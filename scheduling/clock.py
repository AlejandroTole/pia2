"""Control de horario de trading (sesiones y días permitidos).
 
Convierte el instante actual (UTC) a la zona horaria configurada (ej.
America/Toronto) y decide si estamos dentro de una ventana de trading.
"""
 
from __future__ import annotations
 
from datetime import datetime, time
from zoneinfo import ZoneInfo
 
from config.schema import ScheduleConfig
 
_DAY_INDEX = {"Mon": 0, "Tue": 1, "Wed": 2, "Thu": 3, "Fri": 4, "Sat": 5, "Sun": 6}
 
 
def _parse_hhmm(value: str) -> time:
    hour, minute = value.split(":")
    return time(int(hour), int(minute))
 
 
def within_session(now_utc: datetime, schedule: ScheduleConfig) -> bool:
    """True si `now_utc` cae en un día permitido y dentro de alguna sesión."""
    tz = ZoneInfo(schedule.timezone)
    local = now_utc.astimezone(tz)
 
    allowed_days = {_DAY_INDEX[d] for d in schedule.trade_days if d in _DAY_INDEX}
    if local.weekday() not in allowed_days:
        return False
 
    current = local.time()
    for session in schedule.sessions:
        start = _parse_hhmm(session.start)
        end = _parse_hhmm(session.end)
        if start <= end:
            if start <= current <= end:
                return True
        else:
            # Sesión que cruza medianoche.
            if current >= start or current <= end:
                return True
    return False
 
 
def is_trading_time(schedule: ScheduleConfig, now_utc: datetime | None = None) -> bool:
    now = now_utc or datetime.now(ZoneInfo("UTC"))
    if now.tzinfo is None:
        now = now.replace(tzinfo=ZoneInfo("UTC"))
    return within_session(now, schedule)