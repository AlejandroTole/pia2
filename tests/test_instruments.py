from pia2.market.instruments import (
    SymbolSpec,
    money_profit,
    normalize_volume,
    price_to_pips,
)
 
 
def eurusd_spec():
    # EURUSD: 5 dígitos, point 0.00001, tick_value 1.0 por lote estándar.
    return SymbolSpec(
        name="EURUSD", digits=5, point=0.00001, tick_size=0.00001, tick_value=1.0,
        contract_size=100000, volume_min=0.01, volume_max=100, volume_step=0.01,
    )
 
 
def usdjpy_spec():
    # USDJPY: 3 dígitos, point 0.001.
    return SymbolSpec(
        name="USDJPY", digits=3, point=0.001, tick_size=0.001, tick_value=0.9,
        contract_size=100000, volume_step=0.01,
    )
 
 
def xauusd_spec():
    # Oro: 2 dígitos, point 0.01.
    return SymbolSpec(
        name="XAUUSD", digits=2, point=0.01, tick_size=0.01, tick_value=1.0,
        contract_size=100, volume_step=0.01,
    )
 
 
def test_pip_size_varies_by_symbol():
    assert eurusd_spec().pip_size == 0.0001   # 5 dígitos -> pip = 10 points
    assert usdjpy_spec().pip_size == 0.01     # 3 dígitos -> pip = 10 points
    assert xauusd_spec().pip_size == 0.01     # 2 dígitos -> pip = 1 point
 
 
def test_price_to_pips_eurusd():
    spec = eurusd_spec()
    assert round(price_to_pips(spec, 0.0010), 1) == 10.0
 
 
def test_money_profit_buy_win():
    spec = eurusd_spec()
    # +0.0010 (10 pips) con 1 lote y tick_value 1.0/tick 0.00001 = 100 ticks * 1.0
    profit = money_profit(spec, "BUY", 1.10000, 1.10100, 1.0)
    assert round(profit, 2) == 100.0
 
 
def test_money_profit_sell_win():
    spec = eurusd_spec()
    profit = money_profit(spec, "SELL", 1.10100, 1.10000, 1.0)
    assert round(profit, 2) == 100.0
 
 
def test_money_profit_loss():
    spec = eurusd_spec()
    profit = money_profit(spec, "BUY", 1.10100, 1.10000, 1.0)
    assert round(profit, 2) == -100.0
 
 
def test_normalize_volume_respects_step_and_min():
    spec = eurusd_spec()
    assert normalize_volume(spec, 0.004) == 0.01   # sube al mínimo
    assert normalize_volume(spec, 0.126) == 0.13   # redondea al step