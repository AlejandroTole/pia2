import json
from datetime import datetime, timezone

from pia2.news.cross_analyzer import NewsCrossAnalyzer
from pia2.news.store import NewsEvent


def test_news_cross_analyzer_builds_bias(tmp_path):
    features_dir = tmp_path / "features"
    features_dir.mkdir(parents=True, exist_ok=True)

    # Serie M15 ascendente para que la reacción promedio sea BUY.
    rows = []
    price = 1.1000
    for i in range(40):
        rows.append({
            "time": f"2026-07-01 {(i // 4):02d}:{(i % 4) * 15:02d}:00",
            "close": round(price, 5),
        })
        price += 0.0005

    path = features_dir / "EURUSD.PRO.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rows, f)

    analyzer = NewsCrossAnalyzer(str(features_dir))
    events = [
        NewsEvent(
            title="US CPI beats forecast",
            source="rss",
            published_at=datetime(2026, 7, 1, 1, 0, tzinfo=timezone.utc),
            impact="HIGH",
            sentiment="BULLISH",
            symbols="EURUSD.PRO",
        ),
        NewsEvent(
            title="FOMC statement",
            source="rss",
            published_at=datetime(2026, 7, 1, 2, 0, tzinfo=timezone.utc),
            impact="HIGH",
            sentiment="NEUTRAL",
            symbols="EURUSD.PRO",
        ),
    ]

    summary = analyzer.summarize_for_symbol(
        symbol="EURUSD.PRO",
        events=events,
        windows_minutes=[15, 60, 240],
        min_events=2,
    )
    assert summary["bias"] == "BUY"
    assert summary["events_used"] >= 2
