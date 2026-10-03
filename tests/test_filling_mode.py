"""Tests para select_filling_mode (brokers/mt5_broker.py).

`symbol_info.filling_mode` es un bitmask de modos permitidos; el request de
orden necesita UN modo concreto. Estos tests fijan la política:
FOK -> IOC -> RETURN, con fallback seguro a IOC.
"""

from types import SimpleNamespace

import pytest

from pia2.brokers.mt5_broker import select_filling_mode


@pytest.fixture
def mt5():
    # ORDER_FILLING es una enumeración; symbol_info.filling_mode es un bitmask.
    return SimpleNamespace(
        ORDER_FILLING_FOK=0,
        ORDER_FILLING_IOC=1,
        ORDER_FILLING_RETURN=2,
        SYMBOL_TRADE_EXECUTION_MARKET=2,
    )


def test_none_falls_back_to_ioc(mt5):
    assert select_filling_mode(mt5, None) == mt5.ORDER_FILLING_IOC


def test_garbage_falls_back_to_ioc(mt5):
    assert select_filling_mode(mt5, "no-es-un-numero") == mt5.ORDER_FILLING_IOC


def test_zero_flags_falls_back_to_ioc(mt5):
    assert select_filling_mode(mt5, 0, mt5.SYMBOL_TRADE_EXECUTION_MARKET) == mt5.ORDER_FILLING_IOC


def test_single_ioc(mt5):
    assert select_filling_mode(mt5, 2) == mt5.ORDER_FILLING_IOC


def test_single_return(mt5):
    assert select_filling_mode(mt5, 0, trade_execution=0) == mt5.ORDER_FILLING_RETURN


def test_fok_preferred_over_ioc(mt5):
    flags = 1 | 2
    assert select_filling_mode(mt5, flags) == mt5.ORDER_FILLING_FOK


def test_fok_preferred_over_return(mt5):
    flags = 1 | 4
    assert select_filling_mode(mt5, flags) == mt5.ORDER_FILLING_FOK


def test_ioc_preferred_over_return(mt5):
    flags = 2 | 4
    assert select_filling_mode(mt5, flags) == mt5.ORDER_FILLING_IOC


def test_result_is_single_mode_not_bitmask(mt5):
    # El valor devuelto debe ser exactamente uno de los modos, nunca el
    # bitmask crudo combinado.
    flags = 1 | 2 | 4
    result = select_filling_mode(mt5, flags)
    assert result in (mt5.ORDER_FILLING_FOK, mt5.ORDER_FILLING_IOC, mt5.ORDER_FILLING_RETURN)
    assert result != flags
