# Aegis Alpha

Aegis Alpha is an explainable, fail-closed options agent for the 2026 Alpaca AI Trading
Agents Hackathon. It evaluates SPY and QQQ five-minute market regimes, constructs
defined-risk debit spreads, asks a constrained ranker to choose only among valid
candidates, applies deterministic risk gates, and submits exclusively to Alpaca paper
trading.

> **Paper trading only.** This project is educational software, not investment advice.
> Paper results do not represent live-market performance.

## Safety contract

- Live endpoints and `ALPACA_LIVE_TRADE=true` are rejected at startup.
- `DRY_RUN=true` is the default.
- The LLM cannot create contracts, set position size, or bypass the risk guard.
- Missing/stale data, malformed model output, CLI disagreement, and API failures produce
  `NO_TRADE`.
- Every order has an idempotent client order ID and is recorded in SQLite.

## Quick start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
aegis-alpha preflight
aegis-alpha demo
python -m streamlit run app.py
```

Do not add credentials until the offline demo and test suite pass. See
[`docs/OPERATIONS.md`](docs/OPERATIONS.md) for the paper-account activation procedure.

## Architecture

```text
Alpaca market data
  -> Regime agent
  -> Defined-risk candidate agent
  -> Constrained ranker
  -> Structural critic
  -> Deterministic risk guard
  -> Alpaca paper executor
  -> SDK/CLI reconciliation
  -> SQLite audit log + sanitized dashboard export
```

## Commands

| Command | Purpose |
| --- | --- |
| `aegis-alpha preflight` | Validate paper-only configuration and connectivity. |
| `aegis-alpha demo` | Run a fully offline, synthetic dry-run cycle. |
| `aegis-alpha cycle --dry-run` | Evaluate current Alpaca data without submitting. |
| `aegis-alpha cycle --execute` | Submit only after explicit paper-account setup. |
| `aegis-alpha schedule --dry-run` | Run guarded five-minute cycles. |
| `aegis-alpha replay --input PATH` | Replay JSON market-day fixtures. |
| `aegis-alpha reconcile` | Compare SDK and CLI account/position/order views. |
| `aegis-alpha export` | Write a credential-free dashboard snapshot. |

## Current validation boundary

As of September 1, 2026, 28 tests pass, one credential-gated paper integration test is
skipped, all five synthetic replay regimes pass, and measured coverage is 72%. The
dashboard has also been smoke-tested locally from a sanitized export.

A real Alpaca paper lifecycle, CLI authentication, MCP inspection, hosted dashboard, and
competition-account P&L require the participant's credentials and are not claimed until
they are run and recorded.

## Submission packages

- [PowerPoint deck](artifacts/submission/Aegis_Alpha_Hackathon_Deck.pptx)
- [Generated cover image](artifacts/submission/aegis-alpha-cover.png)
- [One-page technical write-up](output/pdf/Aegis_Alpha_Technical_Writeup.pdf)
- [Submission copy](docs/SUBMISSION_DRAFT.md)
- [Video script](docs/VIDEO_SCRIPT.md)
- [MCP setup](docs/MCP_SETUP.md)
