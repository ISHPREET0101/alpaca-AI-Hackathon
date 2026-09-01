# Aegis Alpha — AI Logic, Risk Gates, and Alpaca Infrastructure

**Aegis Alpha** is an autonomous, explainable paper-options agent built for Alpaca. It
seeks directional opportunities in SPY and QQQ while limiting every position to a
precomputed maximum loss. The system trades only bull-call and bear-put debit spreads;
it never creates naked short-option exposure.

## AI logic

Every five minutes, the agent collects Alpaca bars and option-chain snapshots. A regime
agent combines EMA9/EMA21 direction, session VWAP, RSI14, realized volatility, and minimum
trend strength to label each underlying bullish, bearish, or neutral. Neutral regimes
produce no trade. A candidate agent then constructs only same-expiry spreads with 7–21
days to expiry, a long-leg delta near 0.45, tradable contracts, fresh quotes, and positive
debit pricing.

The language model is deliberately constrained: it receives a numbered list of candidates
and may return only a selected index, thesis, confidence, evidence, and invalidation. A
separate critic checks structure, direction, duplicate exposure, and liquidity. Missing
data, malformed model output, or uncertainty produces `NO_TRADE`.

## Deterministic risk gates

Risk is enforced in unit-tested Python with no model in the loop. Planned loss is capped
at the lower of $500 or 0.5% of equity. Aggregate open risk is capped at $1,500 with at
most three positions, one new position per underlying per day, and a 30-minute cooldown.
The agent rejects quotes older than 60 seconds, bid/ask width above 15% of the spread
midpoint, new entries after 3:30 PM ET, and all entries after a 1.5% daily drawdown. The
position monitor targets +40% or −30% on premium. A kill switch halts new orders.

## Alpaca infrastructure

`alpaca-py` supplies typed Trading and Market Data clients, option chains with Greeks,
account/clock/position truth, and atomic `mleg` limit orders. Every order uses a stable
client order ID, preventing duplicate retries. The Alpaca CLI independently retrieves
account, position, and open-order JSON; disagreement with the SDK halts new orders and is
recorded. Alpaca MCP exposes account, options, market-data, and order inspection during
the demo without bypassing the risk engine.

SQLite records every proposal, veto, risk gate, order, fill status, request ID, and
reconciliation. The public Streamlit dashboard reads a sanitized export, not credentials
or the private database. All execution is restricted in code to Alpaca's paper endpoint.
Paper P&L is simulated evidence only and is not presented as expected live performance.

