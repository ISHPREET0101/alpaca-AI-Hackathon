from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

PAPER_BASE_URL = "https://paper-api.alpaca.markets"


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    api_key: str = ""
    secret_key: str = ""
    paper: bool = True
    base_url: str = PAPER_BASE_URL
    data_feed: str = "iex"
    cli_path: str = "alpaca"
    cli_profile: str = ""
    cli_version: str = "latest-tested-manually"
    database_path: Path = Path("data/aegis_alpha.db")
    dry_run: bool = True
    kill_switch: bool = False
    competition_account_id: str = ""
    starting_equity: float = 100_000.0
    ranker_mode: str = "llm"
    llm_api_key: str = ""
    llm_base_url: str = "https://api.featherless.ai/v1"
    llm_model: str = ""
    underlyings: tuple[str, ...] = ("SPY", "QQQ")
    cycle_seconds: int = 300
    target_delta: float = 0.45
    min_dte: int = 7
    max_dte: int = 21
    max_trade_risk_pct: float = 0.005
    max_trade_risk_dollars: float = 500.0
    max_aggregate_risk: float = 1_500.0
    max_positions: int = 3
    daily_drawdown_limit: float = 0.015
    cooldown_minutes: int = 30
    max_quote_age_seconds: int = 60
    max_quote_width_ratio: float = 0.15
    take_profit_pct: float = 0.40
    stop_loss_pct: float = -0.30
    force_exit_hour: int = 15
    force_exit_minute: int = 45
    market_timezone: str = "America/New_York"
    metadata: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_env(cls, env_file: str | Path | None = ".env") -> Settings:
        if env_file:
            load_dotenv(env_file, override=False)
        return cls(
            api_key=os.getenv("ALPACA_API_KEY", ""),
            secret_key=os.getenv("ALPACA_SECRET_KEY", ""),
            paper=_bool("ALPACA_PAPER", True),
            base_url=os.getenv("ALPACA_BASE_URL", PAPER_BASE_URL).rstrip("/"),
            data_feed=os.getenv("ALPACA_DATA_FEED", "iex"),
            cli_path=os.getenv("ALPACA_CLI_PATH", "alpaca"),
            cli_profile=os.getenv("ALPACA_CLI_PROFILE", ""),
            cli_version=os.getenv("ALPACA_CLI_VERSION", "latest-tested-manually"),
            database_path=Path(os.getenv("DATABASE_PATH", "data/aegis_alpha.db")),
            dry_run=_bool("DRY_RUN", True),
            kill_switch=_bool("KILL_SWITCH", False),
            competition_account_id=os.getenv("COMPETITION_ACCOUNT_ID", ""),
            starting_equity=float(os.getenv("COMPETITION_STARTING_EQUITY", "100000")),
            ranker_mode=os.getenv("RANKER_MODE", "llm").strip().lower(),
            llm_api_key=os.getenv("LLM_API_KEY", ""),
            llm_base_url=os.getenv("LLM_BASE_URL", "https://api.featherless.ai/v1").rstrip("/"),
            llm_model=os.getenv("LLM_MODEL", ""),
        )

    def validate_safety(self, require_credentials: bool = False) -> None:
        if not self.paper:
            raise ValueError("Live trading is permanently disabled: ALPACA_PAPER must be true")
        if self.base_url != PAPER_BASE_URL:
            raise ValueError(f"Only the Alpaca paper endpoint is allowed: {PAPER_BASE_URL}")
        if os.getenv("ALPACA_LIVE_TRADE", "").strip().lower() == "true":
            raise ValueError("ALPACA_LIVE_TRADE=true is forbidden")
        if require_credentials and (not self.api_key or not self.secret_key):
            raise ValueError("ALPACA_API_KEY and ALPACA_SECRET_KEY are required")
        if self.ranker_mode not in {"llm", "rule"}:
            raise ValueError("RANKER_MODE must be 'llm' or 'rule'")
