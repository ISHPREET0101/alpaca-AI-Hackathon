# Operations Runbook

## 1. Install and validate offline

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
pytest
aegis-alpha replay --input fixtures\replay_scenarios.json
aegis-alpha demo
python -m streamlit run app.py
```

The installed Alpaca Python SDK is pinned by the project range and was validated locally
against `alpaca-py 0.44.0`.

## 2. Install Alpaca CLI

The official CLI requires Go on Windows:

```powershell
go install github.com/alpacahq/cli/cmd/alpaca@v0.0.13
alpaca version
alpaca profile login
alpaca account get
alpaca clock
```

Paper trading is the CLI default. Do not use `--live`, and keep
`ALPACA_LIVE_TRADE=false`. The project refuses to operate if that environment variable is
true. The CLI is alpha software; `v0.0.13` is the version documented for this build and
must be revalidated before upgrading.

## 3. Configure the development paper account

1. Copy `.env.example` to `.env`.
2. Add the disposable paper account key and secret.
3. Leave `DRY_RUN=true`, `ALPACA_PAPER=true`, and the paper base URL unchanged.
4. Set `ALPACA_CLI_PROFILE` if the authenticated CLI profile is not the default.
5. Run `aegis-alpha preflight`.
6. Run `aegis-alpha cycle --dry-run` during market hours.

## 4. Configure the fresh competition account

1. Create a brand-new paper account and confirm the starting equity is exactly $100,000.
2. Replace only the local `.env` credentials.
3. Set `COMPETITION_ACCOUNT_ID` to the new account UUID.
4. Set the LLM provider values and keep `RANKER_MODE=llm`.
5. Run `aegis-alpha preflight`; every check must pass.
6. Run `aegis-alpha cycle --dry-run` and inspect `artifacts/public/dashboard.json`.
7. Only then use:

```powershell
aegis-alpha cycle --execute --confirm-paper
aegis-alpha schedule --execute --confirm-paper
```

Both execution flags are required. This is a paper-only confirmation, not permission for
live trading.

## 5. Emergency response

1. Set `KILL_SWITCH=true` and stop the scheduler with Ctrl+C.
2. Inspect the Alpaca dashboard before changing orders or positions.
3. Use `alpaca order list --status open` and `alpaca position list` for independent truth.
4. Do not use `close-all` or `cancel-all` until the exact targets are reviewed.
5. Record the incident and any manual action in the demo notes.

## 6. Public dashboard

```powershell
aegis-alpha export --output artifacts\public\dashboard.json
python -m streamlit run app.py
```

Deploy only `app.py`, the source package, and `artifacts/public/dashboard.json`. Never
deploy `.env`, SQLite databases, CLI profiles, raw API logs, or screenshots containing
the account ID.

