"""Servicio de noticias: captura, histórico y decisión para trading."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from config.schema import NewsConfig
from pia2.ai.analyst import Analysis
from pia2.news.collector import NewsCollector
from pia2.news.cross_analyzer import NewsCrossAnalyzer
from pia2.news.store import NewsStore


@dataclass
class NewsDecision:
    should_block: bool = False
    block_reason: str = ""
    historical_bias: str = "NEUTRAL"
    historical_confidence: float = 0.0
    context_text: str = ""


class NewsService:
    def __init__(
        self,
        cfg: NewsConfig,
        symbols: list[str],
        store: NewsStore | None = None,
        collector: NewsCollector | None = None,
        analyzer: NewsCrossAnalyzer | None = None,
    ):
        self.cfg = cfg
        self.symbols = symbols
        self.store = store or NewsStore()
        self.collector = collector or NewsCollector()
        self.analyzer = analyzer or NewsCrossAnalyzer()
        self._last_refresh: datetime | None = None

    def refresh_if_due(self, now_utc: datetime) -> int:
        if not self.cfg.enabled:
            return 0

        if self._last_refresh is not None:
            elapsed = now_utc - self._last_refresh
            if elapsed < timedelta(minutes=self.cfg.refresh_minutes):
                return 0

        start = now_utc - timedelta(days=self.cfg.historical_lookback_days)
        calendar_start = now_utc - timedelta(
            days=min(self.cfg.calendar_scan_days, self.cfg.historical_lookback_days)
        )
        rss_events = self.collector.fetch_rss(self.cfg.rss_urls, self.symbols)
        cal_events = self.collector.fetch_calendar_html(calendar_start, now_utc, self.symbols)
        manual_events = self.collector.fetch_manual_events(self.cfg.manual_events, self.symbols)
        inserted = self.store.upsert_events(rss_events + cal_events + manual_events)
        self._last_refresh = now_utc
        return inserted

    def build_decision(self, symbol: str, now_utc: datetime) -> NewsDecision:
        if not self.cfg.enabled:
            return NewsDecision(context_text="Módulo de noticias desactivado.")

        block = self.store.blocking_event(
            symbol=symbol,
            now_utc=now_utc,
            high_before_min=self.cfg.block_high_before_minutes,
            high_after_min=self.cfg.block_high_after_minutes,
            medium_enabled=self.cfg.block_medium_enabled,
            med_before_min=self.cfg.block_medium_before_minutes,
            med_after_min=self.cfg.block_medium_after_minutes,
        )

        start = now_utc - timedelta(days=self.cfg.historical_lookback_days)
        events = self.store.events_between(start, now_utc)
        summary = self.analyzer.summarize_for_symbol(
            symbol=symbol,
            events=events,
            windows_minutes=self.cfg.reaction_windows_minutes,
            min_events=self.cfg.min_pattern_events,
        )

        decision = NewsDecision(
            should_block=bool(block and self.cfg.use_filter),
            block_reason=(
                f"Bloqueo por noticia {block.impact}: {block.title}" if block and self.cfg.use_filter else ""
            ),
            historical_bias=summary.get("bias", "NEUTRAL"),
            historical_confidence=float(summary.get("confidence", 0.0)),
            context_text=summary.get("summary", "Sin contexto de noticias."),
        )
        return decision

    def apply_confidence_policy(self, analysis: Analysis, decision: NewsDecision) -> Analysis:
        if not self.cfg.enabled or not self.cfg.use_confidence_adjustment:
            return analysis
        if analysis.signal not in {"BUY", "SELL"}:
            return analysis
        if decision.historical_bias == "NEUTRAL" or decision.historical_confidence <= 0:
            return analysis

        if analysis.signal == decision.historical_bias:
            analysis.confidence = min(100.0, analysis.confidence + self.cfg.confidence_boost_aligned)
            analysis.reason = (
                f"{analysis.reason} | Noticias históricas alineadas (+{self.cfg.confidence_boost_aligned})"
            ).strip(" |")
        else:
            analysis.confidence = max(0.0, analysis.confidence - self.cfg.confidence_penalty_conflict)
            analysis.reason = (
                f"{analysis.reason} | Noticias históricas en contra (-{self.cfg.confidence_penalty_conflict})"
            ).strip(" |")
        return analysis
