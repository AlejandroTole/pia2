import pandas as pd

from config.loader import load_config
from pia2.agents.historical_agent.multi_historical_builder import MultiHistoricalBuilder


def _load_test_config():
    # config.yaml es local (no se sube al repo); en CI/clon fresco se usa el ejemplo.
    from pathlib import Path
    path = Path("config/config.yaml")
    if not path.exists():
        path = Path("config/config.example.yaml")
    return load_config(str(path))


def test_builder_uses_yaml_config_for_indicators_and_thresholds():
    cfg = _load_test_config()
    builder = MultiHistoricalBuilder(config=cfg)

    rows = []
    price = 1.0
    start = pd.Timestamp("2024-01-01 00:00:00")
    for i in range(200):
        price += 0.0002 + (0.00005 if i % 8 == 0 else 0.0)
        rows.append(
            {
                "time": start + pd.Timedelta(minutes=15 * i),
                "open": price - 0.0001,
                "high": price + 0.0007,
                "low": price - 0.0007,
                "close": price,
                "volume": 100,
            }
        )

    df = pd.DataFrame(rows)
    prepared = builder.prepare_feature_frame(df)

    assert {"EMA_FAST", "EMA_SLOW", "RSI", "ATR", "trend", "future_move", "future_result"}.issubset(prepared.columns)
    assert prepared["RSI"].dropna().notna().all()
    assert prepared["ATR"].dropna().notna().all()
    assert prepared["future_result"].isin(["BUY", "SELL", None]).all()
    assert builder.min_future_move_atr_ratio == cfg.historical.min_future_move_atr_ratio
