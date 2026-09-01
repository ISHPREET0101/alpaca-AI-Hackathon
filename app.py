from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

SNAPSHOT_PATH = Path("artifacts/public/dashboard.json")

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
columns = st.columns(4)
columns[0].metric(
    "Latest equity",
    f"${summary.get('latest_equity', 0):,.2f}" if summary.get("latest_equity") else "—",
)
columns[1].metric("Agent decisions", summary.get("decision_count", 0))
columns[2].metric("Execution records", summary.get("execution_count", 0))
matched = summary.get("last_reconciliation_matched")
columns[3].metric(
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

with st.expander("Execution and reconciliation audit"):
    st.markdown("**Executions**")
    st.dataframe(pd.DataFrame(snapshot.get("executions", [])), width="stretch")
    st.markdown("**Reconciliations**")
    st.dataframe(pd.DataFrame(snapshot.get("reconciliations", [])), width="stretch")

st.caption(f"Snapshot generated: {snapshot.get('generated_at', 'unknown')}")
