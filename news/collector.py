"""Recolector gratuito de noticias (RSS + calendario web público)."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree as ET

import requests

from pia2.news.store import NewsEvent


_HIGH_IMPACT_KEYWORDS = (
    "interest rate",
    "rate decision",
    "fomc",
    "nfp",
    "non-farm",
    "cpi",
    "inflation",
    "gdp",
    "employment",
    "unemployment",
    "powell",
    "ecb",
    "boe",
    "boj",
    "boc",
)

_MEDIUM_IMPACT_KEYWORDS = (
    "pmi",
    "retail sales",
    "consumer confidence",
    "speech",
    "minutes",
    "manufacturing",
    "services",
)

_BULLISH_KEYWORDS = ("beats", "strong", "rises", "hawkish", "optimistic")
_BEARISH_KEYWORDS = ("misses", "weak", "falls", "dovish", "recession")


class NewsCollector:
    def __init__(self, timeout: int = 20):
        self.timeout = timeout

    def fetch_rss(self, urls: list[str], symbols: list[str]) -> list[NewsEvent]:
        events: list[NewsEvent] = []
        for url in urls:
            try:
                resp = requests.get(url, timeout=self.timeout)
                resp.raise_for_status()
            except requests.RequestException:
                continue

            try:
                root = ET.fromstring(resp.content)
            except ET.ParseError:
                continue

            for item in root.findall(".//item"):
                title = (item.findtext("title") or "").strip()
                if not title:
                    continue
                pub = item.findtext("pubDate") or item.findtext("published") or ""
                published_at = self._parse_datetime(pub)
                link = (item.findtext("link") or "").strip()

                impact = classify_impact(title)
                sentiment = classify_sentiment(title)
                affected = infer_symbols(title, symbols)

                events.append(
                    NewsEvent(
                        title=title,
                        source=_source_from_url(url),
                        published_at=published_at,
                        impact=impact,
                        sentiment=sentiment,
                        symbols=",".join(affected),
                        url=link,
                    )
                )
        return events

    def fetch_calendar_html(
        self,
        start_utc: datetime,
        end_utc: datetime,
        symbols: list[str],
    ) -> list[NewsEvent]:
        """Best-effort scraper de calendario público de ForexFactory.

        Nota: al ser scraping sin API, el sitio puede cambiar su HTML.
        En ese caso retorna [] y el sistema sigue funcionando con RSS.
        """
        events: list[NewsEvent] = []
        day = start_utc.date()
        while day <= end_utc.date():
            day_url = f"https://www.forexfactory.com/calendar?day={day.strftime('%b%d.%Y').lower()}"
            try:
                resp = requests.get(day_url, timeout=self.timeout, headers={"User-Agent": "Mozilla/5.0"})
                resp.raise_for_status()
            except requests.RequestException:
                day += timedelta(days=1)
                continue

            rows = re.findall(r"<tr[^>]*calendar__row[^>]*>(.*?)</tr>", resp.text, re.DOTALL)
            for row in rows:
                title = _clean_html(_extract_first(row, r"calendar__event[^>]*>(.*?)<"))
                if not title:
                    continue
                currency = _clean_html(_extract_first(row, r"calendar__currency[^>]*>(.*?)<"))
                impact_txt = _clean_html(_extract_first(row, r"calendar__impact[^>]*title=\"([^\"]+)\""))
                time_txt = _clean_html(_extract_first(row, r"calendar__time[^>]*>(.*?)<"))

                if not time_txt or time_txt.lower() in {"all day", "tentative"}:
                    continue

                published_at = _parse_day_time_utc(day, time_txt)
                impact = "HIGH" if "high" in impact_txt.lower() else "MEDIUM"
                sentiment = classify_sentiment(title)
                affected = map_currency_to_symbols(currency, symbols)
                events.append(
                    NewsEvent(
                        title=title,
                        source="ForexFactory",
                        published_at=published_at,
                        impact=impact,
                        sentiment=sentiment,
                        symbols=",".join(affected),
                        url=day_url,
                    )
                )
            day += timedelta(days=1)
        return events

    def fetch_manual_events(self, manual_entries: list[dict], symbols: list[str]) -> list[NewsEvent]:
        """Acepta un conjunto de eventos estructurados desde el YAML.

        Ejemplo de entrada:
        {
          "title": "ECB rate decision",
          "published_at": "2026-07-20T12:00:00+02:00",
          "impact": "HIGH",
          "sentiment": "NEUTRAL",
          "symbols": "EURUSD.PRO"
        }
        """
        events: list[NewsEvent] = []
        for item in manual_entries or []:
            if not isinstance(item, dict):
                continue
            published_at = _parse_iso_datetime(item.get("published_at"))
            symbol_csv = _normalize_symbols_field(item.get("symbols"), symbols)
            events.append(
                NewsEvent(
                    title=str(item.get("title") or "Manual news event"),
                    source=str(item.get("source") or "manual"),
                    published_at=published_at,
                    impact=str(item.get("impact") or "MEDIUM").upper(),
                    sentiment=str(item.get("sentiment") or "NEUTRAL").upper(),
                    symbols=symbol_csv,
                    url=str(item.get("url") or ""),
                )
            )
        return events

    @staticmethod
    def _parse_datetime(value: str) -> datetime:
        if not value:
            return datetime.now(timezone.utc)
        try:
            dt = parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return datetime.now(timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)


def classify_impact(title: str) -> str:
    text = title.lower()
    if any(k in text for k in _HIGH_IMPACT_KEYWORDS):
        return "HIGH"
    if any(k in text for k in _MEDIUM_IMPACT_KEYWORDS):
        return "MEDIUM"
    return "LOW"


def classify_sentiment(title: str) -> str:
    text = title.lower()
    if any(k in text for k in _BULLISH_KEYWORDS):
        return "BULLISH"
    if any(k in text for k in _BEARISH_KEYWORDS):
        return "BEARISH"
    return "NEUTRAL"


def infer_symbols(title: str, symbols: list[str]) -> list[str]:
    text = title.upper()
    out = []
    for symbol in symbols:
        base = symbol.split(".")[0]
        if len(base) < 6:
            continue
        c1, c2 = base[:3], base[3:6]
        if c1 in text or c2 in text:
            out.append(symbol)
        elif "XAU" in base and ("GOLD" in text or "XAU" in text):
            out.append(symbol)
    return out


def map_currency_to_symbols(currency: str, symbols: list[str]) -> list[str]:
    c = (currency or "").upper().strip()
    if not c:
        return symbols
    result = []
    for symbol in symbols:
        base = symbol.split(".")[0]
        if c in base:
            result.append(symbol)
        elif c == "XAU" and base.startswith("XAU"):
            result.append(symbol)
    return result or symbols


def _source_from_url(url: str) -> str:
    clean = re.sub(r"^https?://", "", url).split("/")[0]
    return clean or "rss"


def _clean_html(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _extract_first(text: str, pattern: str) -> str:
    m = re.search(pattern, text, re.DOTALL)
    return m.group(1) if m else ""


def _parse_day_time_utc(day, time_txt: str) -> datetime:
    # Formatos observados: "8:30am", "10:00pm".
    clean = time_txt.strip().lower().replace(" ", "")
    try:
        tm = datetime.strptime(clean, "%I:%M%p").time()
    except ValueError:
        return datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
    return datetime(day.year, day.month, day.day, tm.hour, tm.minute, tzinfo=timezone.utc)


def _parse_iso_datetime(value: str | datetime | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip()
        if not text:
            return datetime.now(timezone.utc)
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            return datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _normalize_symbols_field(value, known_symbols: list[str]) -> str:
    if value is None:
        return ",".join(known_symbols)
    if isinstance(value, str):
        parts = [p.strip() for p in value.split(",") if p.strip()]
    elif isinstance(value, (list, tuple, set)):
        parts = [str(p).strip() for p in value if str(p).strip()]
    else:
        parts = [str(value).strip()]
    cleaned = [p.upper() for p in parts if p]
    if not cleaned:
        return ",".join(known_symbols)
    return ",".join(cleaned)
