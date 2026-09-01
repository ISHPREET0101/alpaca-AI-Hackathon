# Demo Video Script — 4:30 Target

## 0:00–0:30 — Problem

“AI trading systems are good at proposing trades, but a convincing autonomous agent also
needs to explain when it refuses to trade. Aegis Alpha is a paper-options agent built on
Alpaca that separates probabilistic reasoning from deterministic risk.”

## 0:30–1:30 — Architecture

Show the architecture slide and code tree. Explain the regime agent, bounded candidate
generator, constrained ranker, critic, risk guard, executor, CLI reconciler, monitor, and
audit store. Emphasize that the model selects an index only.

## 1:30–2:30 — Decision and gates

Open the dashboard. Show the latest SPY or QQQ regime, AI thesis, confidence, chosen legs,
maximum loss, and gate table. Then show a deliberately stale-quote or kill-switch test
producing `NO_TRADE`.

## 2:30–3:30 — Alpaca implementation

Show the paper account and an atomic multi-leg order. Run `aegis-alpha reconcile` and show
matching SDK/CLI state. Use MCP to inspect account equity, current positions, the option
chain, and the same client order ID. Do not place a new order through MCP.

## 3:30–4:15 — Results and honesty

Show the equity curve, realized/unrealized paper P&L, fills, and decision log. State the
evaluation period and trade count. Explain that paper fills and the short sample do not
prove live profitability.

## 4:15–4:30 — Close

“Aegis Alpha is autonomous where speed matters, deterministic where safety matters, and
fully inspectable where trust matters.”

