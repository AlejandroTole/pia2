import pandas as pd

from config.schema import PIAConfig
from pia2.strategy.interpreter import reference_trade_signal, build_reference_setup


def test_reference_trade_signal_uses_ema_rsi_and_candle_bias():
    signal = reference_trade_signal(
        price=1.1000,
        ema_fast=1.1010,
        ema_slow=1.0990,
        rsi=62,
        atr=0.0008,
        candle_context={"bias": "BUY", "strength": 80},
    )

    assert signal == "BUY"


def test_reference_trade_setup_matches_atr_based_sl_tp():
    cfg = PIAConfig().indicators
    setup = build_reference_setup(
        price=1.1000,
        atr=0.0008,
        signal="BUY",
        cfg=cfg,
    )

    assert setup.valid is True
    assert setup.signal == "BUY"
    assert setup.stop_loss < setup.entry < setup.take_profit
    assert setup.sl_distance == cfg.atr_sl_multiplier * 0.0008
    assert setup.tp_distance == cfg.atr_tp_multiplier * 0.0008
