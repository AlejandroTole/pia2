from datetime import datetime, timezone

from config.schema import NewsConfig
from pia2.ai.analyst import Analysis
from pia2.news.service import NewsDecision, NewsService
from pia2.news.store import NewsEvent, NewsStore


def test_news_service_blocks_high_impact(tmp_path):
    db = tmp_path / "news.db"
    store = NewsStore(str(db))
    cfg = NewsConfig(enabled=True, use_filter=True)
    service = NewsService(cfg=cfg, symbols=["EURUSD.PRO"], store=store)

    now = datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc)
    store.upsert_events([
        NewsEvent(
            title="US CPI release",
            source="calendar",
            published_at=now,
            impact="HIGH",
            sentiment="NEUTRAL",
            symbols="EURUSD.PRO",
        )
    ])

    decision = service.build_decision("EURUSD.PRO", now)
    assert decision.should_block is True
    assert "Bloqueo por noticia HIGH" in decision.block_reason
    store.close()


def test_news_confidence_adjustment_aligned(tmp_path):
    cfg = NewsConfig(enabled=True, use_confidence_adjustment=True, confidence_boost_aligned=6)
    store = NewsStore(str(tmp_path / "news.db"))
    service = NewsService(cfg=cfg, symbols=["EURUSD.PRO"], store=store)
    analysis = Analysis(signal="BUY", confidence=70, reason="base")
    decision = NewsDecision(historical_bias="BUY", historical_confidence=55)

    out = service.apply_confidence_policy(analysis, decision)
    assert out.confidence == 76
    store.close()


def test_news_confidence_adjustment_conflict(tmp_path):
    cfg = NewsConfig(enabled=True, use_confidence_adjustment=True, confidence_penalty_conflict=10)
    store = NewsStore(str(tmp_path / "news.db"))
    service = NewsService(cfg=cfg, symbols=["EURUSD.PRO"], store=store)
    analysis = Analysis(signal="BUY", confidence=70, reason="base")
    decision = NewsDecision(historical_bias="SELL", historical_confidence=70)

    out = service.apply_confidence_policy(analysis, decision)
    assert out.confidence == 60
    store.close()


def test_news_service_accepts_manual_structured_events(tmp_path):
    db = tmp_path / "news.db"
    store = NewsStore(str(db))
    now = datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc)
    cfg = NewsConfig(
        enabled=True,
        use_filter=True,
        rss_urls=[],
        manual_events=[{
            "title": "ECB rate decision",
            "source": "manual",
            "published_at": "2026-07-20T12:00:00+00:00",
            "impact": "HIGH",
            "sentiment": "NEUTRAL",
            "symbols": "EURUSD.PRO",
        }],
    )
    service = NewsService(cfg=cfg, symbols=["EURUSD.PRO"], store=store)

    inserted = service.refresh_if_due(now)
    assert inserted == 1

    decision = service.build_decision("EURUSD.PRO", now)
    assert decision.should_block is True
    assert "ECB rate decision" in decision.block_reason
    store.close()
