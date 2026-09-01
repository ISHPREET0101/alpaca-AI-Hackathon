# Aegis Alpha Architecture

## Design goal

Aegis Alpha demonstrates autonomous options trading without allowing a language model to
control portfolio risk. Alpaca provides the market data, paper execution, account truth,
CLI reconciliation, and MCP inspection surface.

## Decision flow

1. **Market data adapter** retrieves five-minute SPY/QQQ bars and option-chain snapshots.
2. **Regime agent** classifies bullish, bearish, or neutral from EMA9/EMA21, session VWAP,
   RSI14, realized volatility, and minimum trend-separation rules.
3. **Candidate agent** creates only same-expiry bull-call or bear-put debit spreads with
   7–21 days to expiry and a long delta near 0.45.
4. **Ranker** chooses an index from the supplied candidates and returns a strict JSON
   thesis. It cannot alter contracts, price, size, or limits.
5. **Critic** rejects contradictory direction, duplicate exposure, invalid expiries, or
   malformed debit structures.
6. **Risk guard** calculates size and evaluates every non-negotiable gate.
7. **Executor** creates an atomic two-leg `mleg` limit order with an idempotent client ID.
8. **Reconciler** compares SDK account/position truth with independent Alpaca CLI JSON.
9. **Monitor** reprices open spreads and creates a closing multi-leg order at configured
   profit or loss thresholds.
10. **Audit store** records decisions, gates, executions, request IDs, reconciliation, and
    errors in SQLite. Public export removes credentials and pseudonymizes account IDs.

## Trust boundaries

- The LLM receives derived market context and valid candidates, never credentials.
- Alpaca credentials exist only in process environment or Alpaca's local profile store.
- The Streamlit dashboard consumes a sanitized static JSON snapshot and cannot trade.
- MCP is restricted to judge-facing inspection; it is not called by the risk-critical
  executor.
- Any missing dependency, data mismatch, stale quote, or uncertain model result halts new
  orders.

## State and recovery

SQLite uses WAL mode. A cycle lock prevents overlapping schedulers. Client order IDs are
derived from the five-minute cycle, underlying, and leg symbols, so ambiguous retries do
not create a second order. Open-trade intents retain enough information for a restarted
monitor to reconstruct exit legs.

