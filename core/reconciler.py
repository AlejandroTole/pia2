"""Cierre de operaciones y cálculo de resultado REAL.
 
Dos caminos:
- REAL: lee las operaciones cerradas por el broker (deal history) y actualiza
  el resultado con el P/L real de MT5.
- DEMO: como no hay órdenes reales, evalúa cada operación simulada contra las
  velas posteriores y la cierra cuando el precio toca SL o TP, calculando el
  P/L con las specs reales del símbolo (no con `* 10000` como la v1).
"""
 
from __future__ import annotations
 
from dataclasses import replace
from datetime import datetime, timedelta, timezone
 
import pandas as pd

from pia2.brokers.base import BrokerInterface
from config.schema import PIAConfig
from pia2.market.instruments import money_profit
from pia2.memory.store import TradeStore
from pia2.risk.risk_guard import RiskGuard

# Inicio de la cuenta demo: el backfill reconcilia el historial desde aquí.
DEMO_START = datetime(2026, 10, 5, tzinfo=timezone.utc)
 
 
def reconcile(config: PIAConfig, broker: BrokerInterface, store: TradeStore,
              guard: RiskGuard, last_check: datetime | None = None) -> int:
    """Actualiza resultados de operaciones cerradas. Devuelve cuántas cerró."""
    if config.is_real:
        return _reconcile_real(config, broker, store, guard, last_check)
    return _reconcile_demo(config, broker, store, guard)
 
 
def _reconcile_real(config, broker, store, guard, last_check) -> int:
    # Usar últimas 7 días si no hay último check, para evitar errores de MT5 con fechas muy antiguas
    since = last_check or (datetime.now(timezone.utc) - timedelta(days=7))
    return _reconcile_deals(config, broker, store, guard, since)


def backfill_history(config, broker, store, guard, since: datetime = DEMO_START) -> int:
    """Reconcilia TODO el historial de deals desde `since`, insertando los faltantes.

    Es idempotente: las filas que ya existen no se duplican. Devuelve cuántos
    trades se cerraron, insertaron, resolvieron (UNKNOWN) o corrigieron.
    """
    return _reconcile_deals(config, broker, store, guard, since, repair=True)


def _group_by_position(deals) -> list:
    """Une los cierres parciales de una misma posición en un solo deal neto."""
    grouped: dict[int, list] = {}
    for deal in deals:
        grouped.setdefault(deal.ticket, []).append(deal)
    merged = []
    for parts in grouped.values():
        if len(parts) == 1:
            merged.append(parts[0])
            continue
        parts.sort(key=lambda d: d.close_time)
        last = parts[-1]
        volume = sum(d.volume for d in parts)
        exit_price = (
            sum(d.exit_price * d.volume for d in parts) / volume if volume > 0 else last.exit_price
        )
        merged.append(replace(
            last,
            volume=volume,
            exit_price=exit_price,
            profit=sum(d.profit for d in parts),
            commission=sum(d.commission for d in parts),
            swap=sum(d.swap for d in parts),
            fee=sum(d.fee for d in parts),
        ))
    return merged


def _reconcile_deals(config, broker, store, guard, since, repair: bool = False) -> int:
    deals = broker.closed_deals_since(since, magic=config.magic_number)
    try:
        open_tickets = {position.ticket for position in broker.open_positions()}
    except (AttributeError, RuntimeError):
        open_tickets = None
    closed = 0
    deal_tickets = set()
    for deal in _group_by_position(deals):
        deal_tickets.add(deal.ticket)
        net_profit = deal.profit + deal.commission + deal.swap + deal.fee
        status = "WIN" if net_profit > 0 else ("LOSS" if net_profit < 0 else "BREAKEVEN")
        if store.update_result_by_ticket(
            deal.ticket,
            status,
            deal.exit_price,
            net_profit,
            closed_at=deal.close_time.isoformat(),
        ):
            guard.register_closed_pnl(net_profit, closed_at=deal.close_time)
            closed += 1
        elif store.resolve_unknown_by_ticket(
            deal.ticket, status, deal.exit_price, net_profit,
            deal.close_time.isoformat(),
        ):
            # Fila marcada UNKNOWN cuyo deal real apareció después.
            guard.register_closed_pnl(net_profit, closed_at=deal.close_time)
            closed += 1
        elif store.has_ticket(deal.ticket):
            # Solo en la reparación: alinear filas ya cerradas con el deal real.
            if repair and store.correct_closed_by_ticket(
                deal.ticket, status, deal.exit_price, net_profit,
                deal.close_time.isoformat(),
            ):
                closed += 1
        elif (
            deal.magic == config.magic_number
            # Con la posición aún abierta el deal es un cierre parcial: no está completo.
            and not (open_tickets is not None and deal.ticket in open_tickets)
            and store.insert_closed_trade(
                ticket=deal.ticket,
                symbol=deal.symbol,
                direction=deal.direction,
                volume=deal.volume,
                entry_price=deal.entry_price,
                exit_price=deal.exit_price,
                profit=net_profit,
                status=status,
                closed_at=deal.close_time.isoformat(),
                opened_at=deal.open_time.isoformat() if deal.open_time else "",
                reason="Recuperado del historial del broker (sin registro local)",
                context={"source": "broker_deal_backfill"},
            )
        ):
            guard.register_closed_pnl(net_profit, closed_at=deal.close_time)
            closed += 1
    if open_tickets is not None:
        for trade in store.pending():
            if (
                trade.ticket is not None
                and trade.ticket not in open_tickets
                and trade.ticket not in deal_tickets
            ):
                store.mark_unknown_by_ticket(trade.ticket)
    return closed
 
 
def _reconcile_demo(config, broker, store, guard) -> int:
    closed = 0
    for trade in store.pending():
        # Un trade con ticket pertenece al broker real y no debe ser simulado.
        if trade.ticket is not None:
            continue
        spec = broker.symbol_spec(trade.symbol)
        if spec is None:
            continue
        df = broker.get_candles(trade.symbol, config.timeframe, config.candles)
        if df is None or df.empty:
            continue
 
        exit_price = _find_exit(df, trade)
        if exit_price is None:
            continue
 
        profit = money_profit(spec, trade.direction, trade.entry_price, exit_price, trade.volume)
        status = "WIN" if profit > 0 else ("LOSS" if profit < 0 else "BREAKEVEN")
        # Operaciones simuladas se identifican por id (no hay ticket de broker).
        if store.update_result_by_id(trade.id, status, exit_price, profit):
            guard.register_closed_pnl(profit)
            closed += 1
    return closed
 
 
def _find_exit(df: pd.DataFrame, trade) -> float | None:
    """Busca en las velas si el precio tocó SL o TP tras la entrada.
 
    Recorre las velas posteriores a la de apertura (si se guardó bar_time) y
    devuelve el precio de salida (SL o TP), priorizando el SL cuando ambos
    caben en la misma vela (postura conservadora).
    """
    bar_time = trade.context.get("bar_time")
    candles = df
    if bar_time is not None and "time" in df.columns:
        try:
            cutoff = pd.to_datetime(bar_time)
            candles = df[df["time"] > cutoff]
        except (ValueError, TypeError):
            candles = df
 
    for _, row in candles.iterrows():
        high = float(row["high"])
        low = float(row["low"])
        if trade.direction == "BUY":
            if low <= trade.stop_loss:
                return trade.stop_loss
            if high >= trade.take_profit:
                return trade.take_profit
        else:  # SELL
            if high >= trade.stop_loss:
                return trade.stop_loss
            if low <= trade.take_profit:
                return trade.take_profit
    return None
 
 
 