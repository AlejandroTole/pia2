from datetime import date, datetime, timezone

from config.schema import RiskConfig
from core.orchestrator import _default_stop_file
from risk.risk_guard import RiskGuard


def test_default_stop_file_is_in_repository_root():
    assert (_default_stop_file().parent / "pyproject.toml").exists()


def test_risk_guard_uses_configured_local_date():
    now = datetime(2026, 9, 28, 2, 0, tzinfo=timezone.utc)
    guard = RiskGuard(RiskConfig(), timezone_name="America/Toronto")

    assert guard.local_date(now) == date(2026, 9, 27)
    assert now.date() == date(2026, 9, 28)