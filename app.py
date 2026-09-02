from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

SNAPSHOT_PATH = Path("artifacts/public/dashboard.json")
REPLAY_PATH = Path("artifacts/public/replay_report.json")

st.set_page_config(page_title="Aegis Alpha", page_icon="🛡️", layout="wide")
st.title("🛡️ Aegis Alpha")
st.caption("Explainable autonomous options agent · Alpaca paper trading only")
st.warning(
    "Educational paper-trading prototype. Simulated results do not predict live-market performance."
)

if not SNAPSHOT_PATH.exists():
    st.info("No public snapshot exists yet. Run `aegis-alpha demo` or `aegis-alpha export`.")
    st.stop()

snapshot = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
summary = snapshot.get("summary", {})
columns = st.columns(5)
columns[0].metric(
    "Latest equity",
    f"${summary.get('latest_equity', 0):,.2f}" if summary.get("latest_equity") else "—",
)
columns[1].metric("Agent decisions", summary.get("decision_count", 0))
paper_pnl = summary.get("paper_pnl_since_first_snapshot")
columns[2].metric(
    "Paper P&L in snapshot",
    f"${paper_pnl:,.2f}" if paper_pnl is not None else "—",
)
columns[3].metric("Active trades", summary.get("active_trade_count", 0))
matched = summary.get("last_reconciliation_matched")
columns[4].metric(
    "SDK ↔ CLI", "Matched" if matched is True else "Unavailable" if matched is None else "HALTED"
)

decisions = snapshot.get("decisions", [])
if decisions:
    latest = decisions[0].get("payload", {})
    st.subheader("Latest agent cycle")
    left, right = st.columns([2, 1])
    with left:
        st.markdown(f"**{latest.get('underlying', '—')} · {latest.get('action', '—')}**")
        st.write(latest.get("reason", ""))
        ranker = latest.get("ranker", {})
        st.markdown("**AI thesis**")
        st.write(ranker.get("thesis", "No thesis available"))
        source = ranker.get("source", "unknown")
        confidence = ranker.get("confidence", 0)
        st.caption(f"Source: {source} · Confidence: {confidence:.0%}")
    with right:
        regime = latest.get("regime", {})
        st.metric("Regime", str(regime.get("regime", "—")).title())
        st.metric("RSI", f"{regime.get('rsi', 0):.1f}")
        st.metric("Realized volatility", f"{regime.get('realized_volatility', 0):.1%}")

    st.subheader("Deterministic risk gates")
    checks = latest.get("risk_state", {}).get("checks", [])
    if checks:
        frame = pd.DataFrame(checks)
        frame["status"] = frame["passed"].map({True: "PASS", False: "BLOCK"})
        st.dataframe(frame[["status", "name", "detail"]], width="stretch", hide_index=True)

st.subheader("Decision history")
history = [
    {
        "time": row.get("created_at"),
        "underlying": row.get("underlying"),
        "action": row.get("action"),
        "reason": row.get("reason"),
    }
    for row in decisions
]
if history:
    st.dataframe(pd.DataFrame(history), width="stretch", hide_index=True)
else:
    st.info("No decisions have been exported.")

st.subheader("Trade lifecycle ledger")
trades = snapshot.get("trades", [])
if trades:
    trade_frame = pd.DataFrame(trades)
    visible = [
        column
        for column in (
            "opened_at",
            "underlying",
            "strategy",
            "expiry",
            "quantity",
            "entry_debit",
            "risk_dollars",
            "status",
        )
        if column in trade_frame.columns
    ]
    st.dataframe(trade_frame[visible], width="stretch", hide_index=True)
else:
    st.info("No simulated or paper trades are present in this snapshot.")

with st.expander("Execution and reconciliation audit"):
    st.markdown("**Executions**")
    st.dataframe(pd.DataFrame(snapshot.get("executions", [])), width="stretch")
    st.markdown("**Reconciliations**")
    st.dataframe(pd.DataFrame(snapshot.get("reconciliations", [])), width="stretch")

if REPLAY_PATH.exists():
    replay = json.loads(REPLAY_PATH.read_text(encoding="utf-8"))
    replay_summary = replay.get("summary", {})
    st.subheader("Offline verification evidence")
    replay_columns = st.columns(3)
    replay_columns[0].metric("Replay scenarios", replay_summary.get("scenario_count", 0))
    replay_columns[1].metric("Expected regimes matched", replay_summary.get("matched_count", 0))
    replay_columns[2].metric(
        "Classification accuracy",
        f"{replay_summary.get('classification_accuracy', 0):.0%}",
    )
    st.info(replay.get("warning", "Replay results are not a live-performance claim."))
    replay_rows = [
        {
            "scenario": item.get("name"),
            "expected": item.get("expected"),
            "actual": item.get("actual"),
            "matched": item.get("matched"),
            "source": item.get("data_source"),
        }
        for item in replay.get("results", [])
    ]
    if replay_rows:
        st.dataframe(pd.DataFrame(replay_rows), width="stretch", hide_index=True)

st.caption(f"Snapshot generated: {snapshot.get('generated_at', 'unknown')}")
