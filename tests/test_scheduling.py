from datetime import datetime
from zoneinfo import ZoneInfo
 
from config.schema import ScheduleConfig, Session
from pia2.scheduling.clock import within_session
 
 
def schedule():
    return ScheduleConfig(
        timezone="America/Toronto",
        sessions=[Session("08:00", "11:00")],
        trade_days=["Mon", "Tue", "Wed", "Thu", "Fri"],
    )
 
 
def toronto(y, m, d, hh, mm):
    return datetime(y, m, d, hh, mm, tzinfo=ZoneInfo("America/Toronto")).astimezone(ZoneInfo("UTC"))
 
 
def test_within_session_true():
    # Viernes 2026-07-17 09:00 Toronto
    assert within_session(toronto(2026, 7, 17, 9, 0), schedule()) is True
 
 
def test_outside_session_hours():
    assert within_session(toronto(2026, 7, 17, 12, 0), schedule()) is False
 
 
def test_weekend_blocked():
    # Sábado 2026-07-18 09:00 Toronto
    assert within_session(toronto(2026, 7, 18, 9, 0), schedule()) is False