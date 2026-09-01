# Alpaca MCP Demo Setup

The MCP server is an inspection and demonstration layer. It is intentionally outside the
agent's deterministic execution path.

Prerequisites: Python 3.10+, `uv`/`uvx`, paper account keys, and an MCP-compatible client.
Copy `.vscode/mcp.example.json` to `.vscode/mcp.json`, replace the placeholders locally,
and never commit the resulting file.

Enabled toolsets:

```text
account,trading,assets,stock-data,options-data
```

Judge-facing demo prompts:

1. “Show the paper account equity, buying power, and portfolio history.”
2. “List current option positions and open orders.”
3. “Show the SPY option chain and Greeks for the contracts used in the latest decision.”
4. “Show recent order activity and match it to the dashboard's client order ID.”

Do not ask MCP to generate or submit a new trade during the demo. A judge should see that
the LLM can inspect Alpaca, while every autonomous order still comes through Aegis Alpha's
critic and deterministic risk guard.

