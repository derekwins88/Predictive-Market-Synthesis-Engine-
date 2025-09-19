# sim/engine.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from .metrics import daily_roi_df, equity_stats


# --- simple indicators (vectorized) ---
def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()


def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    delta = close.diff()
    up = (delta.where(delta > 0, 0)).rolling(n).mean()
    down = (-delta.where(delta < 0, 0)).rolling(n).mean()
    rs = up / (down.replace(0, np.nan))
    out = 100 - (100 / (1 + rs))
    return out.fillna(50.0)


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [
            (high - low),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.rolling(n).mean()


# --- broker model (very small, close-to-close fills) ---
@dataclass
class Position:
    qty: int = 0
    avg_price: float = 0.0


class Broker:
    def __init__(
        self,
        cash: float,
        commission_per_contract: float = 2.0,
        slippage_ticks: float = 1.0,
        tick_value: float = 12.5,
        tick_size: float = 0.25,
    ):
        self.cash = float(cash)
        self.equity = float(cash)
        self.pos = Position()
        self.commission = commission_per_contract
        self.slip_ticks = slippage_ticks
        self.tick_value = tick_value
        self.tick_size = tick_size
        self.trades: list[dict] = []
        self._equity_curve: list[tuple[pd.Timestamp, float]] = []

    def _slip_price(self, px: float, side: str) -> float:
        slip = self.slip_ticks * self.tick_size
        return px + (slip if side == "BUY" else -slip)

    def mark(self, ts: pd.Timestamp, last_price: float):
        # mark-to-market equity
        if self.pos.qty != 0:
            pnl_per = (last_price - self.pos.avg_price) * np.sign(self.pos.qty)
            position_value = pnl_per * abs(self.pos.qty) * (self.tick_value / self.tick_size)
        else:
            position_value = 0.0
        self.equity = self.cash + position_value
        self._equity_curve.append((ts, self.equity))

    def buy(self, ts: pd.Timestamp, px: float, qty: int):
        fill_px = self._slip_price(px, "BUY")
        fees = self.commission * qty
        dollar_mult = self.tick_value / self.tick_size
        # adjust avg
        new_qty = self.pos.qty + qty
        if self.pos.qty == 0:
            new_avg = fill_px
        else:
            new_avg = (self.pos.avg_price * self.pos.qty + fill_px * qty) / new_qty
        self.pos = Position(qty=new_qty, avg_price=new_avg)
        self.cash -= fees
        self.trades.append(
            {
                "ts": ts,
                "side": "BUY",
                "qty": qty,
                "price": fill_px,
                "fees": fees,
                "mult": dollar_mult,
            }
        )

    def sell(self, ts: pd.Timestamp, px: float, qty: int):
        fill_px = self._slip_price(px, "SELL")
        fees = self.commission * qty
        dollar_mult = self.tick_value / self.tick_size
        # close or reduce long
        realized = 0.0
        if self.pos.qty > 0:
            close_qty = min(qty, self.pos.qty)
            realized = (fill_px - self.pos.avg_price) * close_qty * dollar_mult
            self.pos.qty -= close_qty
        else:
            # shorting not implemented in first pack; keep long-only
            pass
        self.cash += realized - fees
        self.trades.append(
            {
                "ts": ts,
                "side": "SELL",
                "qty": qty,
                "price": fill_px,
                "fees": fees,
                "realized": realized,
                "mult": dollar_mult,
            }
        )

    @property
    def equity_curve(self) -> pd.Series:
        if not self._equity_curve:
            return pd.Series(dtype=float)
        idx = pd.to_datetime([t for t, _ in self._equity_curve], utc=True)
        val = [v for _, v in self._equity_curve]
        return pd.Series(val, index=idx).sort_index()


# --- Strategy contract (imported at runtime) ---
class Context:
    def __init__(
        self,
        cash: float,
        position_qty: int,
        position_avg: float | None,
        day_pnl: float,
        realized_dd_pct: float,
        regime: str,
    ):
        self.cash = cash
        self.position_qty = position_qty
        self.position_avg = position_avg
        self.day_pnl = day_pnl
        self.realized_dd_pct = realized_dd_pct
        self.regime = regime


def classify_regime(atr_to_close: float) -> str:
    if atr_to_close < 0.005:
        return "Calm"
    if atr_to_close < 0.010:
        return "Fractal"
    return "Cascade"


def run_once(
    bars: pd.DataFrame,
    strategy_obj: Any,
    cash: float = 100_000.0,
    commission: float = 2.0,
    slippage_ticks: float = 1.0,
    rsi_period: int = 14,
    ema_fast: int = 20,
    ema_slow: int = 50,
    atr_period: int = 14,
) -> dict:
    """
    bars: DataFrame with columns [timestamp, open, high, low, close, volume]
          utc timestamps expected
    strategy_obj: instance implementing .on_bar(df_row, ctx) -> list[OrderDict]
    """
    df = bars.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.sort_values("timestamp").reset_index(drop=True)
    # indicators
    df["ema_fast"] = ema(df["close"], ema_fast)
    df["ema_slow"] = ema(df["close"], ema_slow)
    df["rsi"] = rsi(df["close"], rsi_period)
    df["atr"] = atr(df[["high", "low", "close"]], atr_period)
    df["atr_to_close"] = df["atr"] / df["close"]
    # broker
    broker = Broker(
        cash=cash,
        commission_per_contract=commission,
        slippage_ticks=slippage_ticks,
    )
    day_start_equity = cash
    peak_equity = cash

    for i, row in df.iterrows():
        ts = row["timestamp"]
        atr_to_close = row["atr_to_close"]
        if pd.notna(atr_to_close):
            regime = classify_regime(atr_to_close)
        else:
            regime = "Calm"
        broker.mark(ts, float(row["close"]))

        # session/day tracking
        date = ts.date()
        if i == 0 or df.loc[i - 1, "timestamp"].date() != date:
            day_start_equity = broker.equity
        peak_equity = max(peak_equity, broker.equity)
        if peak_equity == 0:
            dd_pct = 0.0
        else:
            dd_pct = max(0.0, (peak_equity - broker.equity) / peak_equity * 100.0)

        ctx = Context(
            cash=broker.cash,
            position_qty=broker.pos.qty,
            position_avg=(None if broker.pos.qty == 0 else broker.pos.avg_price),
            day_pnl=broker.equity - day_start_equity,
            realized_dd_pct=dd_pct,
            regime=regime,
        )

        # delegate to strategy (expects dict orders: {'side': 'BUY'|'SELL', 'qty': int})
        orders: list[dict] = strategy_obj.on_bar(row, ctx) or []
        for od in orders:
            side = od.get("side")
            qty = int(max(0, od.get("qty", 0)))
            if qty <= 0:
                continue
            if side == "BUY":
                broker.buy(ts, float(row["close"]), qty)
            elif side == "SELL":
                broker.sell(ts, float(row["close"]), qty)

    equity = broker.equity_curve
    daily = daily_roi_df(equity)
    stats = equity_stats(equity)

    return {
        "daily": daily.to_dict(orient="records"),
        "summary": stats,
        "meta": {
            "bars": len(df),
            "start": df["timestamp"].iloc[0].isoformat(),
            "end": df["timestamp"].iloc[-1].isoformat(),
            "strategy": getattr(strategy_obj, "name", "Unknown"),
        },
    }
