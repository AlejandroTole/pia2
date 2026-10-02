"""RiskGuard: gobernanza de riesgo a nivel cuenta (circuit breakers).
 
Independiente del tamaño de una operación individual (eso es RiskManager),
RiskGuard protege la CUENTA:
  - Límite de pérdida diaria -> detiene el trading hasta el día siguiente.
  - Drawdown máximo desde el pico de equity -> pausa total.
  - Máximo de operaciones por día.
  - Máximo de posiciones abiertas simultáneas.
  - Filtro de spread.
  - Filtro de horario (dentro de sesión permitida).
 
Mantiene estado diario y se reinicia al cambiar de día.
"""
 
from __future__ import annotations
 
from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo
 
from config.schema import RiskConfig
 
 
@dataclass
class GuardDecision:
    allowed: bool
    reason: str
 
 
class RiskGuard:
    def __init__(self, risk: RiskConfig, store=None, timezone_name: str = "UTC"):
        self.risk = risk
        self.store = store
        self.timezone_name = timezone_name
        self._timezone = ZoneInfo(timezone_name)
        self._day: date | None = None
        self._day_start_balance: float = 0.0
        self._realized_pnl_today: float = 0.0
        self._trades_today: int = 0
        self._peak_equity: float = 0.0

        self._restore_state()

    def local_date(self, moment: datetime) -> date:
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=ZoneInfo("UTC"))
        return moment.astimezone(self._timezone).date()

    def _persist_state(self) -> None:
        if self.store is None:
            return
        self.store.save_guard_state(
            self._day.isoformat() if self._day else None,
            self._day_start_balance,
            self._realized_pnl_today,
            self._trades_today,
            self._peak_equity,
        )

    def _restore_state(self) -> None:
        if self.store is None:
            return
        state = self.store.load_guard_state()
        if state is None or not state.get("day"):
            return
        self._day = date.fromisoformat(state["day"])
        self._day_start_balance = float(state["day_start_balance"])
        self._realized_pnl_today = float(state["realized_pnl_today"])
        self._trades_today = int(state["trades_today"])
        self._peak_equity = float(state["peak_equity"])
 
    # ---------- estado diario ----------
 
    def start_day(self, today: date, balance: float) -> None:
        if self._day == today and self._day_start_balance > 0:
            self.update_equity(balance)
            return
        self._day = today
        self._day_start_balance = balance
        self._realized_pnl_today = 0.0
        self._trades_today = 0
        if self._peak_equity <= 0:
            self._peak_equity = balance
        self._persist_state()
 
    def _ensure_day(self, today: date, balance: float) -> None:
        if self._day != today:
            self.start_day(today, balance)
 
    def register_trade_opened(self) -> None:
        self._trades_today += 1
        self._persist_state()
 
    def register_closed_pnl(self, profit: float, closed_at: datetime | None = None) -> None:
        if closed_at is not None and self._day is not None:
            if self.local_date(closed_at) != self._day:
                return
        self._realized_pnl_today += profit
        self._persist_state()
 
    def update_equity(self, equity: float) -> None:
        if equity > self._peak_equity:
            self._peak_equity = equity
            self._persist_state()
 
    # ---------- métricas ----------
 
    @property
    def trades_today(self) -> int:
        return self._trades_today
 
    def daily_loss_pct(self, equity: float | None = None) -> float:
        """Pérdida diaria usando equity cuando está disponible."""
        if self._day_start_balance <= 0:
            return 0.0
        if equity is None:
            loss = -self._realized_pnl_today
        else:
            loss = self._day_start_balance - equity
        return max(0.0, (loss / self._day_start_balance) * 100.0)
 
    def drawdown_pct(self, equity: float) -> float:
        if self._peak_equity <= 0:
            return 0.0
        if equity >= self._peak_equity:
            return 0.0
        return ((self._peak_equity - equity) / self._peak_equity) * 100.0

    @staticmethod
    def _currency_exposures(symbol: str, direction: str) -> set[tuple[str, str]]:
        clean = "".join(char for char in symbol.upper() if char.isalpha())
        if len(clean) < 6:
            return set()
        base, quote = clean[:3], clean[3:6]
        side = direction.upper()
        opposite = "SELL" if side == "BUY" else "BUY"
        return {(base, side), (quote, opposite)}

    def currency_exposure_allowed(self, symbol: str, direction: str, positions) -> bool:
        requested = self._currency_exposures(symbol, direction)
        if not requested:
            return True
        counts: dict[tuple[str, str], int] = {}
        for position in positions:
            for exposure in self._currency_exposures(position.symbol, position.direction):
                counts[exposure] = counts.get(exposure, 0) + 1
        return all(
            counts.get(exposure, 0) < self.risk.max_same_currency_exposure
            for exposure in requested
        )
 
    # ---------- decisión ----------

    def _max_spread_for_symbol(self, symbol: str | None = None) -> float:
        value = self.risk.max_spread_points
        if isinstance(value, dict):
            if symbol is not None:
                target = symbol.upper()
                for key, limit in value.items():
                    if str(key).upper() == target:
                        return float(limit)
            return float(next(iter(value.values()), 30.0))
        return float(value)
 
    def can_open_trade(
        self,
        today: date,
        balance: float,
        equity: float,
        open_positions: int,
        spread_points: float,
        within_session: bool,
        symbol: str | None = None,
    ) -> GuardDecision:
        self._ensure_day(today, balance)
        self.update_equity(equity)
 
        dd = self.drawdown_pct(equity)
        if dd >= self.risk.max_drawdown_pct:
            return GuardDecision(False, f"Drawdown {dd:.2f}% >= máx {self.risk.max_drawdown_pct}% (pausa total)")
 
        loss = self.daily_loss_pct(equity)
        if loss >= self.risk.max_daily_loss_pct:
            return GuardDecision(False, f"Pérdida diaria {loss:.2f}% >= máx {self.risk.max_daily_loss_pct}% (detenido hoy)")
 
        if self._trades_today >= self.risk.max_trades_per_day:
            return GuardDecision(False, f"Máx operaciones/día alcanzado ({self._trades_today}/{self.risk.max_trades_per_day})")
 
        if open_positions >= self.risk.max_open_positions:
            return GuardDecision(
                False,
                f"Máx posiciones abiertas global ({open_positions}/{self.risk.max_open_positions})",
            )
 
        max_spread = self._max_spread_for_symbol(symbol)
        if spread_points > max_spread:
            return GuardDecision(False, f"Spread {spread_points:.1f} > máx {max_spread} points")
 
        if not within_session:
            return GuardDecision(False, "Fuera de la ventana horaria permitida")
 
        return GuardDecision(True, "OK")
