"""Mide el spread real de un símbolo en MT5.

Uso:
    python tools/measure_spread.py --symbol EURUSD.PRO --days 14
"""

import argparse
import statistics
import time
from datetime import datetime, timedelta, timezone

import MetaTrader5 as mt5


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="EURUSD.PRO")
    parser.add_argument("--days", type=int, default=14)
    args = parser.parse_args()

    if not mt5.initialize():
        print("No se pudo conectar a MT5 (¿terminal abierto y logueado?)")
        return 1

    try:
        info = mt5.symbol_info(args.symbol)
        if info is None:
            print(f"Símbolo no encontrado: {args.symbol}")
            return 1
        if not info.point:
            print(f"Point inválido para el símbolo: {args.symbol}")
            return 1

        now = datetime.now(timezone.utc)
        ticks = mt5.copy_ticks_range(
            args.symbol,
            now - timedelta(days=args.days),
            now,
            mt5.COPY_TICKS_ALL,
        )
        if ticks is not None and len(ticks) > 100:
            spreads = [round((tick.ask - tick.bid) / info.point, 1) for tick in ticks]
            source = f"historial de ticks ({len(spreads)})"
        else:
            print("Sin historial de ticks; muestreo en vivo 3 minutos...")
            spreads = []
            seen = set()
            end_time = time.time() + 180
            while time.time() < end_time:
                tick = mt5.symbol_info_tick(args.symbol)
                if tick is not None:
                    key = (tick.bid, tick.ask, tick.time)
                    if key not in seen:
                        seen.add(key)
                        spreads.append(round((tick.ask - tick.bid) / info.point, 1))
                time.sleep(1)
            source = f"muestreo en vivo ({len(spreads)} ticks)"

        if not spreads:
            print("Sin datos de spread.")
            return 1

        spreads.sort()
        p50 = spreads[len(spreads) // 2]
        p95 = spreads[min(len(spreads) - 1, int(len(spreads) * 0.95))]
        print(f"Símbolo: {args.symbol} | fuente: {source}")
        print(
            f"Spread puntos -> avg={statistics.mean(spreads):.1f} | "
            f"p50={p50:.1f} | p95={p95:.1f}"
        )
        print(f"Recomendado para backtest: --spread-points {p95:.0f}")
    finally:
        mt5.shutdown()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
