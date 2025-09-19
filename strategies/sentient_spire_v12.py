# strategies/sentient_spire_v12.py
from __future__ import annotations

from typing import Any

from .base import Context, Strategy


class SentientSpireV12(Strategy):
    """
    Lean variant of your Echo/Conviction idea:
    - Long-only, trend-aligned (EMA fast>slow) & RSI>55
    - Exit when RSI<45 or regime turns 'Cascade'
    - Risk % sizing against ATR stop distance
    """

    name = "SentientSpire_v12"

    def __init__(self, risk_pct: float = 0.015, stop_atr_mult: float = 1.5, target_r: float = 2.2):
        self.risk_pct = risk_pct
        self.stop_atr_mult = stop_atr_mult
        self.target_r = target_r

    def on_bar(self, bar_row, ctx: Context) -> list[dict[str, Any]]:
        close = float(bar_row["close"])

        if ctx.regime == "Cascade":
            # de-risk: exit if in market
            if ctx.position_qty > 0:
                return [{"side": "SELL", "qty": ctx.position_qty, "price_hint": close}]
            return []

        ema_fast = float(bar_row.get("ema_fast", 0))
        ema_slow = float(bar_row.get("ema_slow", 0))
        rsi = float(bar_row.get("rsi", 50))
        atr = float(bar_row.get("atr", 0.5))

        orders: list[dict[str, Any]] = []

        # Exit rule
        if ctx.position_qty > 0 and rsi < 45:
            orders.append({"side": "SELL", "qty": ctx.position_qty, "price_hint": close})
            return orders

        # Entry rule
        trend_ok = ema_fast > ema_slow
        if trend_ok and rsi > 55 and ctx.position_qty == 0 and atr > 0:
            # position size = risk $ / (stop_distance $)
            stop_dist_px = self.stop_atr_mult * atr
            dollar_per_point = 50.0  # configurable per symbol if needed
            risk_cash = ctx.cash * self.risk_pct
            qty = int(max(1, risk_cash / (stop_dist_px * dollar_per_point)))
            if qty > 0:
                orders.append({"side": "BUY", "qty": qty, "price_hint": close})

        return orders

    def parameters(self) -> dict:
        return {
            "risk_pct": self.risk_pct,
            "stop_atr_mult": self.stop_atr_mult,
            "target_r": self.target_r,
        }
