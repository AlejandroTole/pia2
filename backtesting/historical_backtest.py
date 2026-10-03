"""Backtest histórico basado en los features ya generados por PIA.

Este módulo reusa la lógica operativa principal tanto como es posible con los
datos históricos disponibles en `data/historical/features/*.json`:
build_trade_setup, analyze_candles (+candle policy), RiskGuard, RiskManager,
within_session, min_confidence, block_symbol_stacking y cooldown post-loss.

Limitaciones conocidas (leer antes de confiar en un resultado):
- No hay datos históricos de noticias en esos JSON, así que el filtro de
  noticias queda fuera del replay.
- La señal NO es la del LLM en vivo: aquí la genera el índice de patrones
    históricos (misma idea que HistoricalIntelligence). El backtest valida el
    pipeline determinista (setups, velas, riesgo, costos), NO el juicio del LLM.
    Para validar una variante de estrategia, el LLM debe evaluarse aparte.
- El cálculo de P/L usa las especificaciones inferidas del símbolo (FX / JPY /
  XAU) porque los JSON no contienen las specs del broker.
- Los costos (spread/slippage/comisión) tienen defaults realistas pero son
    aproximados; si el JSON trae columna "spread" por fila, esa manda.

Uso:
    python -m pia2.backtesting.historical_backtest
    python -m pia2.backtesting.historical_backtest --balance 3000 --limits 3 4 6 8
    python -m pia2.backtesting.historical_backtest --symbols XAUUSD.PRO
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd

from config.loader import load_config
from pia2.market.instruments import SymbolSpec, money_profit
from pia2.risk.risk_guard import RiskGuard
from pia2.risk.risk_manager import RiskManager
from pia2.scheduling.clock import within_session
from pia2.strategy.candles import analyze_candles
from pia2.strategy.trade_setup import build_trade_setup


@dataclass
class SignalDecision:
    signal: str = "WAIT"
    confidence: float = 0.0
    reason: str = ""


@dataclass
class OpenTrade:
    symbol: str
    direction: str
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    stop_loss: float
    take_profit: float
    volume: float
    profit: float


@dataclass
class ScenarioResult:
    max_trades_per_day: int
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    breakeven: int = 0
    net_profit: float = 0.0
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    profit_factor: float | None = None
    win_rate: float = 0.0
    max_drawdown_pct: float = 0.0
    average_trades_per_day: float = 0.0
    symbols: dict[str, int] | None = None
    trades_by_day: dict[str, int] | None = None


@dataclass
class SymbolStats:
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    net_profit: float = 0.0

    def win_rate(self) -> float:
        if self.total_trades <= 0:
            return 0.0
        return round((self.wins / self.total_trades) * 100.0, 2)

    def profit_factor(self) -> float | None:
        gross_profit = max(0.0, self.net_profit)
        gross_loss = max(0.0, -self.net_profit)
        if gross_loss <= 0:
            return None
        return round(gross_profit / gross_loss, 2)


class PatternRuntimeIndex:
    def __init__(self, tolerance: float):
        self.tolerance = tolerance
        self._buy_bins: dict[str, list[int]] = {
            "Alcista": [0] * 1001,
            "Bajista": [0] * 1001,
        }
        self._sell_bins: dict[str, list[int]] = {
            "Alcista": [0] * 1001,
            "Bajista": [0] * 1001,
        }

    @staticmethod
    def _bin_index(rsi: float) -> int:
        return max(0, min(1000, int(round(float(rsi) * 10.0))))

    def add(self, trend: str, rsi: float, future_result: str) -> None:
        if trend not in self._buy_bins:
            return
        bin_index = self._bin_index(rsi)
        if future_result == "BUY":
            self._buy_bins[trend][bin_index] += 1
        elif future_result == "SELL":
            self._sell_bins[trend][bin_index] += 1

    def counts(self, trend: str, rsi: float) -> tuple[int, int, int]:
        if trend not in self._buy_bins:
            return 0, 0, 0

        current_bin = self._bin_index(rsi)
        delta = int(round(self.tolerance * 10.0))
        start = max(0, current_bin - delta)
        end = min(1000, current_bin + delta)

        buy_bins = self._buy_bins[trend]
        sell_bins = self._sell_bins[trend]
        buys = sum(buy_bins[start : end + 1])
        sells = sum(sell_bins[start : end + 1])
        total = buys + sells
        return total, buys, sells


def infer_symbol_spec(symbol: str) -> SymbolSpec:
    """Aproxima las specs del símbolo para poder convertir P/L y sizing.

    Los JSON históricos no guardan tick_size/tick_value del broker, así que se
    usa una aproximación razonable para FX/JPY/XAU.
    """

    normalized = symbol.upper()
    if "XAU" in normalized:
        return SymbolSpec(
            name=symbol,
            digits=2,
            point=0.01,
            tick_size=0.01,
            tick_value=1.0,
            contract_size=100.0,
            volume_min=0.01,
            volume_max=100.0,
            volume_step=0.01,
        )
    if "JPY" in normalized:
        return SymbolSpec(
            name=symbol,
            digits=3,
            point=0.001,
            tick_size=0.001,
            tick_value=1.0,
            contract_size=100000.0,
            volume_min=0.01,
            volume_max=100.0,
            volume_step=0.01,
        )
    return SymbolSpec(
        name=symbol,
        digits=5,
        point=0.00001,
        tick_size=0.00001,
        tick_value=1.0,
        contract_size=100000.0,
        volume_min=0.01,
        volume_max=100.0,
        volume_step=0.01,
    )


def load_feature_frame(path: Path) -> pd.DataFrame:
    with open(path, "r", encoding="utf-8") as handle:
        raw = json.load(handle)

    frame = pd.DataFrame(raw)
    if frame.empty:
        return frame

    frame["time"] = pd.to_datetime(frame["time"], utc=True, errors="coerce")
    frame = frame.dropna(subset=["time", "close", "RSI", "ATR", "trend", "future_result"])
    frame = frame.sort_values("time").reset_index(drop=True)
    return frame


def apply_adaptive_confidence(base_confidence: float, stats: SymbolStats) -> float:
    if stats.total_trades < 5:
        return base_confidence

    win_rate = stats.win_rate()
    if win_rate < 45:
        adjusted = base_confidence * 0.8
    elif win_rate < 50:
        adjusted = base_confidence * 0.9
    elif win_rate > 65:
        adjusted = min(100.0, base_confidence * 1.05)
    else:
        adjusted = base_confidence

    return max(0.0, min(100.0, adjusted))


def build_signal_from_counts(
    trend: str,
    rsi: float,
    symbol_stats: SymbolStats,
    cfg,
    pattern_index: PatternRuntimeIndex,
) -> SignalDecision:
    total, buys, sells = pattern_index.counts(trend, rsi)

    if total < cfg.historical.min_patterns:
        return SignalDecision(
            reason=f"Histórico insuficiente ({total} < {cfg.historical.min_patterns})",
        )

    if buys == sells:
        return SignalDecision(reason="Sin ventaja histórica clara")

    buy_probability = (buys / total) * 100.0
    sell_probability = (sells / total) * 100.0

    signal = "BUY" if buy_probability > sell_probability else "SELL"
    base_confidence = abs(buy_probability - sell_probability)
    confidence = apply_adaptive_confidence(base_confidence, symbol_stats)
    return SignalDecision(
        signal=signal,
        confidence=round(confidence, 2),
        reason=(
            f"{total} matches | BUY={buy_probability:.2f}% | SELL={sell_probability:.2f}%"
        ),
    )


def apply_candle_policy(decision: SignalDecision, candle_context: dict, policy) -> SignalDecision:
    if decision.signal not in {"BUY", "SELL"}:
        return decision

    bias = str(candle_context.get("bias", "NEUTRAL")).upper()
    strength = float(candle_context.get("strength", 0) or 0)
    pattern = candle_context.get("pattern", "NONE")

    if bias not in {"BUY", "SELL"} or strength < policy.min_strength:
        return decision

    if decision.signal == bias:
        decision.confidence = min(100.0, decision.confidence + policy.aligned_boost)
        decision.reason = (
            f"{decision.reason} | Velas confirman {bias} ({pattern}, fuerza {int(strength)})"
        )
        return decision

    if strength >= policy.veto_strength:
        return SignalDecision(
            signal="WAIT",
            confidence=0.0,
            reason=f"Veto por velas opuestas {bias} ({pattern}, fuerza {int(strength)})",
        )

    decision.confidence = max(0.0, decision.confidence - policy.conflict_penalty)
    decision.reason = (
        f"{decision.reason} | Velas contradicen ({pattern}, -{policy.conflict_penalty} confianza)"
    )
    return decision


def maybe_close_trades(
    open_trades: list[OpenTrade],
    current_time: datetime,
    balance: float,
    guard: RiskGuard,
    symbol_stats_map: dict[str, SymbolStats],
    equity_curve: list[float],
    last_loss_time: dict[tuple[str, str], datetime] | None = None,
) -> tuple[list[OpenTrade], float]:
    remaining: list[OpenTrade] = []
    for trade in open_trades:
        if trade.exit_time > current_time:
            remaining.append(trade)
            continue

        balance += trade.profit
        guard.register_closed_pnl(trade.profit)

        stats = symbol_stats_map[trade.symbol]
        stats.total_trades += 1
        stats.net_profit += trade.profit
        if trade.profit > 0:
            stats.wins += 1
        elif trade.profit < 0:
            stats.losses += 1
            # Paridad con live (cooldown post-loss): se registra la hora real
            # de cierre, no la barra en que se detectó.
            if last_loss_time is not None:
                last_loss_time[(trade.symbol, trade.direction)] = trade.exit_time

    equity_curve.append(balance)
    return remaining, balance


def calculate_unrealized_pnl(open_trades: list[OpenTrade], latest_prices: dict[str, float]) -> float:
    total = 0.0
    for trade in open_trades:
        current_price = latest_prices.get(trade.symbol)
        if current_price is None:
            continue
        if trade.direction == "BUY":
            total += money_profit(
                infer_symbol_spec(trade.symbol),
                "BUY",
                trade.entry_price,
                current_price,
                trade.volume,
            )
        else:
            total += money_profit(
                infer_symbol_spec(trade.symbol),
                "SELL",
                trade.entry_price,
                current_price,
                trade.volume,
            )
    return total


def simulate_exit(
    frame: pd.DataFrame,
    entry_index: int,
    direction: str,
    stop_loss: float,
    take_profit: float,
) -> tuple[datetime, float]:
    """Resuelve SL/TP con velas posteriores, priorizando SL en empate."""
    last_row = frame.iloc[min(entry_index + 4, len(frame) - 1)]
    for index in range(entry_index + 1, min(entry_index + 5, len(frame))):
        row = frame.iloc[index]
        high = float(row["high"])
        low = float(row["low"])
        if direction == "BUY":
            if low <= stop_loss:
                return row["time"].to_pydatetime(), stop_loss
            if high >= take_profit:
                return row["time"].to_pydatetime(), take_profit
        else:
            if high >= stop_loss:
                return row["time"].to_pydatetime(), stop_loss
            if low <= take_profit:
                return row["time"].to_pydatetime(), take_profit
    return last_row["time"].to_pydatetime(), float(last_row["close"])


def effective_spread(row: pd.Series, default_spread_points: float) -> float:
    """Spread en puntos para una fila del backtest.

    Si el feature JSON trae columna "spread" con valor > 0, manda ese.
    Si no, se usa el default pasado por CLI/config. (Antes el parámetro se
    perdía: la variable local lo sobrescribía siempre con 0.0 cuando la fila
    no traía spread.)
    """
    raw = row.get("spread", None)
    try:
        value = float(raw) if raw not in (None, "") else 0.0
    except (TypeError, ValueError):
        value = 0.0
    return value if value > 0 else float(default_spread_points)


def run_scenario(
    frames_by_symbol: dict[str, pd.DataFrame],
    config,
    max_trades_per_day: int,
    starting_balance: float,
    spread_points: float = 0.0,
    commission_per_lot: float = 0.0,
    slippage_points: float = 0.0,
    train_ratio: float = 0.7,
) -> ScenarioResult:
    risk_cfg = replace(config.risk, max_trades_per_day=max_trades_per_day)
    guard = RiskGuard(risk_cfg)
    # En live, el tope de margen estimado actúa como freno de seguridad.
    # En backtest lo relajamos para comparar símbolos sin ese límite.
    risk_manager = RiskManager(risk_cfg.risk_per_trade_pct, max_margin_per_trade_usd=1e12)

    symbol_stats_map = {symbol: SymbolStats() for symbol in frames_by_symbol}
    event_stream: list[tuple[pd.Timestamp, str, int]] = []
    for symbol, frame in frames_by_symbol.items():
        for index, row in frame.iterrows():
            event_stream.append((row["time"], symbol, int(index)))
    event_stream.sort(key=lambda item: (item[0], item[1]))

    if not event_stream:
        return ScenarioResult(max_trades_per_day=max_trades_per_day, symbols={}, trades_by_day={})

    pattern_indices = {
        symbol: PatternRuntimeIndex(config.historical.rsi_tolerance)
        for symbol in frames_by_symbol
    }

    first_time = event_stream[0][0].to_pydatetime()
    if first_time.tzinfo is None:
        first_time = first_time.replace(tzinfo=timezone.utc)
    guard.start_day(first_time.date(), starting_balance)
    last_time = event_stream[-1][0].to_pydatetime()
    train_until = first_time + (last_time - first_time) * train_ratio

    open_trades: list[OpenTrade] = []
    executed_trades: list[OpenTrade] = []
    balance = starting_balance
    equity_curve: list[float] = [starting_balance]
    latest_prices: dict[str, float] = {}
    trades_by_day: Counter[str] = Counter()
    symbol_counter: Counter[str] = Counter()
    # (símbolo, dirección) -> hora del último cierre con pérdida (cooldown live).
    last_loss_time: dict[tuple[str, str], datetime] = {}

    for event_time, symbol, index in event_stream:
        current_time = event_time.to_pydatetime()
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=timezone.utc)

        # Cierra trades que ya llegaron a su barra de salida.
        open_trades, balance = maybe_close_trades(
            open_trades=open_trades,
            current_time=current_time,
            balance=balance,
            guard=guard,
            symbol_stats_map=symbol_stats_map,
            equity_curve=equity_curve,
            last_loss_time=last_loss_time,
        )

        frame = frames_by_symbol[symbol]
        current_row = frame.iloc[index]
        latest_prices[symbol] = float(current_row["close"])

        # Un resultado solo se conoce cuatro barras después. La fila madura
        # entra al índice justo antes de evaluar la barra actual.
        if index >= 4:
            matured_row = frame.iloc[index - 4]
            pattern_indices[symbol].add(
                str(matured_row["trend"]),
                float(matured_row["RSI"]),
                str(matured_row["future_result"]),
            )

        equity = balance + calculate_unrealized_pnl(open_trades, latest_prices)
        equity_curve.append(equity)

        if not within_session(current_time, config.schedule) or current_time < train_until:
            continue

        if index + 4 >= len(frame):
            continue

        decision = build_signal_from_counts(
            str(current_row["trend"]),
            float(current_row["RSI"]),
            symbol_stats_map[symbol],
            config,
            pattern_indices[symbol],
        )
        candle_context = analyze_candles(frame.iloc[max(0, index - 2) : index + 1])
        decision = apply_candle_policy(decision, candle_context, config.candle_policy)

        if decision.signal == "WAIT":
            continue

        # Paridad con live: umbral mínimo de confianza de la IA.
        if decision.confidence < config.risk.min_confidence:
            continue

        # Paridad con live: sin apilamiento de posiciones por símbolo.
        if config.risk.block_symbol_stacking and any(
            trade.symbol == symbol for trade in open_trades
        ):
            continue

        # Paridad con live: cooldown post-loss por símbolo y dirección.
        cooldown_minutes = config.risk.cooldown_minutes_after_loss
        if cooldown_minutes > 0:
            last_loss = last_loss_time.get((symbol, decision.signal))
            if last_loss is not None and last_loss.tzinfo is None:
                last_loss = last_loss.replace(tzinfo=timezone.utc)
            if last_loss is not None and (current_time - last_loss) < timedelta(
                minutes=cooldown_minutes
            ):
                continue

        spec = infer_symbol_spec(symbol)
        setup = build_trade_setup(spec, decision.signal, float(current_row["close"]), float(current_row["ATR"]), config.indicators)
        if not setup.valid:
            continue

        spread_pts = effective_spread(current_row, spread_points)
        open_positions = len(open_trades)
        guard_decision = guard.can_open_trade(
            today=current_time.date(),
            balance=balance,
            equity=equity,
            open_positions=open_positions,
            spread_points=spread_pts,
            within_session=True,
            symbol=symbol,
        )
        if not guard_decision.allowed:
            continue

        sizing = risk_manager.size(spec, balance, setup.sl_distance, account_leverage=100)
        if not sizing.approved:
            continue

        spread_price = spread_pts * spec.point
        slippage_price = slippage_points * spec.point
        entry_price = float(current_row["close"])
        if decision.signal == "BUY":
            entry_price += spread_price / 2 + slippage_price
        else:
            entry_price -= spread_price / 2 + slippage_price
        exit_time, exit_price = simulate_exit(
            frame, index, decision.signal, setup.stop_loss, setup.take_profit
        )
        profit = money_profit(spec, decision.signal, entry_price, exit_price, sizing.volume)
        profit -= commission_per_lot * sizing.volume

        open_trades.append(
            OpenTrade(
                symbol=symbol,
                direction=decision.signal,
                entry_time=current_time,
                exit_time=exit_time,
                entry_price=entry_price,
                exit_price=exit_price,
                stop_loss=setup.stop_loss,
                take_profit=setup.take_profit,
                volume=sizing.volume,
                profit=profit,
            )
        )
        executed_trades.append(open_trades[-1])
        guard.register_trade_opened()
        trades_by_day[current_time.date().isoformat()] += 1
        symbol_counter[symbol] += 1

    # Cierra los trades que queden abiertos al final del stream.
    for trade in open_trades:
        balance += trade.profit
        guard.register_closed_pnl(trade.profit)
        stats = symbol_stats_map[trade.symbol]
        stats.total_trades += 1
        stats.net_profit += trade.profit
        if trade.profit > 0:
            stats.wins += 1
        elif trade.profit < 0:
            stats.losses += 1

    equity_curve.append(balance)

    total_trades = len(executed_trades)
    wins = sum(1 for trade in executed_trades if trade.profit > 0)
    losses = sum(1 for trade in executed_trades if trade.profit < 0)
    breakeven = total_trades - wins - losses

    net_profit = sum(trade.profit for trade in executed_trades)
    gross_profit = sum(trade.profit for trade in executed_trades if trade.profit > 0)
    gross_loss = -sum(trade.profit for trade in executed_trades if trade.profit < 0)
    profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else None
    win_rate = round((wins / total_trades) * 100.0, 2) if total_trades else 0.0

    peak = equity_curve[0]
    max_drawdown = 0.0
    for value in equity_curve:
        if value > peak:
            peak = value
        if peak > 0:
            max_drawdown = max(max_drawdown, ((peak - value) / peak) * 100.0)

    average_trades_per_day = total_trades / max(1, len(trades_by_day)) if trades_by_day else 0.0

    return ScenarioResult(
        max_trades_per_day=max_trades_per_day,
        total_trades=total_trades,
        wins=wins,
        losses=losses,
        breakeven=breakeven,
        net_profit=round(net_profit, 2),
        gross_profit=round(gross_profit, 2),
        gross_loss=round(gross_loss, 2),
        profit_factor=profit_factor,
        win_rate=win_rate,
        max_drawdown_pct=round(max_drawdown, 2),
        average_trades_per_day=round(average_trades_per_day, 2),
        symbols=dict(symbol_counter),
        trades_by_day=dict(trades_by_day),
    )


def load_frames(project_root: Path, symbols: Iterable[str] | None) -> dict[str, pd.DataFrame]:
    features_dir = project_root / "data" / "historical" / "features"
    selected_symbols = set(symbols or [])
    frames: dict[str, pd.DataFrame] = {}

    for path in sorted(features_dir.glob("*.json")):
        symbol = path.stem
        if selected_symbols and symbol not in selected_symbols:
            continue
        frame = load_feature_frame(path)
        if not frame.empty:
            frames[symbol] = frame

    return frames


def print_result(result: ScenarioResult) -> None:
    profit_factor = result.profit_factor if result.profit_factor is not None else "n/a"
    print(
        f"{result.max_trades_per_day:>5} | "
        f"trades={result.total_trades:>4} | "
        f"win_rate={result.win_rate:>6.2f}% | "
        f"net={result.net_profit:>10.2f} | "
        f"pf={profit_factor!s:>6} | "
        f"dd={result.max_drawdown_pct:>6.2f}% | "
        f"avg/day={result.average_trades_per_day:>5.2f} | "
        f"symbols={result.symbols}"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backtest histórico de PIA 2.0")
    parser.add_argument(
        "--balance",
        type=float,
        default=3000.0,
        help="Balance inicial para el backtest (default: 3000)",
    )
    parser.add_argument(
        "--limits",
        type=int,
        nargs="+",
        default=[3, 4, 6, 8],
        help="Lista de máximos de operaciones por día a comparar",
    )
    parser.add_argument(
        "--symbols",
        nargs="+",
        default=None,
        help="Símbolos a incluir (por defecto: todos los archivos históricos)",
    )
    parser.add_argument("--spread-points", type=float, default=20.0,
                        help="Spread en puntos cuando la fila no trae columna 'spread'. "
                             "20 pts ≈ 2.0 pips en EURUSD de 5 dígitos (demo típico).")
    parser.add_argument("--commission-per-lot", type=float, default=0.0,
                        help="Comisión por lote por operación (ida). Ej: 3.5 ≈ cuenta ECN.")
    parser.add_argument("--slippage-points", type=float, default=10.0,
                        help="Deslizamiento en puntos aplicado a la entrada (10 pts ≈ 1 pip).")
    parser.add_argument(
        "--train-ratio",
        type=float,
        default=0.7,
        help="Fracción inicial reservada para entrenamiento walk-forward.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_root = Path(__file__).resolve().parents[2]
    config = load_config(project_root / "config" / "config.yaml")

    frames = load_frames(project_root, args.symbols or config.broker_symbols())
    if not frames:
        print("No se encontraron features históricos para los símbolos solicitados.")
        return 1

    print("Backtest histórico PIA 2.0")
    print(f"Símbolos: {', '.join(frames.keys())}")
    print(f"Balance inicial: {args.balance:.2f}")
    print("Nota: el filtro de noticias queda fuera porque los features históricos no guardan noticias.")
    print("".ljust(120, "-"))
    print("  max | trades | win_rate |        net |    pf |     dd | avg/day | symbols")
    print("".ljust(120, "-"))

    results = []
    for limit in args.limits:
        scenario_config = replace(config, risk=replace(config.risk, max_trades_per_day=limit))
        result = run_scenario(
            frames,
            scenario_config,
            limit,
            args.balance,
            spread_points=args.spread_points,
            commission_per_lot=args.commission_per_lot,
            slippage_points=args.slippage_points,
            train_ratio=args.train_ratio,
        )
        results.append(result)
        print_result(result)

    best = max(results, key=lambda item: (item.net_profit, -item.max_drawdown_pct, item.win_rate))
    print("".ljust(120, "-"))
    print(
        f"Mejor escenario: max_trades_per_day={best.max_trades_per_day} | "
        f"net={best.net_profit:.2f} | win_rate={best.win_rate:.2f}% | dd={best.max_drawdown_pct:.2f}%"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
