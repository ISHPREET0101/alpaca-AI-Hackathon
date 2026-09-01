# Security Policy

## Supported scope

This hackathon prototype is restricted to Alpaca paper trading. Reports involving secret
exposure, paper/live routing bypass, order duplication, risk-gate bypass, command injection,
or unsafe public exports are high priority.

## Secret handling

- Never commit `.env`, MCP configuration containing keys, CLI profiles, SQLite databases,
  or raw private artifacts.
- Revoke and regenerate any key that appears in Git history, logs, screenshots, or chat.
- The public dashboard must be built only from `aegis-alpha export` output.

## Safety invariants

- Live trading remains disabled.
- No broker order is submitted without deterministic risk approval.
- CLI reconciliation disagreement blocks new orders.
- Model output is validated and cannot define order legs or position size.

