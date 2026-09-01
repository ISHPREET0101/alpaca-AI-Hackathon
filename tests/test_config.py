from __future__ import annotations

from dataclasses import replace

import pytest

from aegis_alpha.config import PAPER_BASE_URL, Settings


def test_default_configuration_is_dry_run_and_paper_only() -> None:
    settings = Settings()
    assert settings.paper is True
    assert settings.dry_run is True
    assert settings.base_url == PAPER_BASE_URL
    settings.validate_safety()


@pytest.mark.parametrize(
    "unsafe",
    [
        replace(Settings(), paper=False),
        replace(Settings(), base_url="https://api.alpaca.markets"),
    ],
)
def test_live_configuration_is_rejected(unsafe: Settings) -> None:
    with pytest.raises(ValueError):
        unsafe.validate_safety()


def test_live_environment_flag_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPACA_LIVE_TRADE", "true")
    with pytest.raises(ValueError):
        Settings().validate_safety()


def test_credentials_can_be_required() -> None:
    with pytest.raises(ValueError, match="required"):
        Settings().validate_safety(require_credentials=True)
