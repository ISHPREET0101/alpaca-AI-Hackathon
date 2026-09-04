# Submission Draft

## Project title

Aegis Alpha — The Options Agent That Can Say No

## Short description

An explainable Alpaca paper-options agent that ranks defined-risk SPY/QQQ debit spreads,
then forces every decision through deterministic risk gates and independent CLI
reconciliation.

## Long description

Most AI trading demos focus on producing a trade. Aegis Alpha focuses on proving why a
trade was allowed—or exactly why it was blocked. Every five minutes it reads Alpaca market
data, classifies the market regime, creates only bounded-loss debit spreads, and asks a
constrained model to rank those valid candidates. The model cannot invent contracts,
change position size, or override a risk rule.

The selected spread must survive a structural critic and deterministic Python controls
for maximum loss, aggregate exposure, drawdown, liquidity, quote freshness, cooldowns,
duplicate orders, and time of day. Orders execute atomically through Alpaca's Trading API.
Alpaca CLI provides an independent account/position/order view; disagreement immediately
halts the agent. Alpaca MCP gives judges a natural-language inspection surface while
remaining outside execution.

The dashboard shows the complete chain of reasoning: regime, candidates, AI thesis,
critic verdict, every passed or failed gate, execution status, reconciliation, and paper
P&L. The result is autonomous behavior with an auditable safety boundary.

## Technology tags

Python, Alpaca Trading API, Alpaca Market Data API, alpaca-py, Alpaca CLI, Alpaca MCP,
Pydantic, pandas, SQLite, Streamlit, AI Agents, Options, FinTech.

## Required values to complete manually

- Public GitHub URL:
- Hosted Streamlit URL: https://aegis-alpha-hackathon.streamlit.app/
- Video URL:
- Slide deck URL/file:
- Fresh $100,000 Alpaca paper account ID:
- Final paper P&L and measurement timestamp:
- Social links:
