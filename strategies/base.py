# strategies/base.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, List, Dict, Any

@dataclass
class Context:
    cash: float
    position_qty: int
    position_avg: Optional[float]
    day_pnl: float
    realized_dd_pct: float
    regime: str

class Strategy:
    name = "BaseStrategy"

    def on_bar(self, bar_row: Any, ctx: Context) -> List[Dict[str, Any]]:
        """
        Return a list of order dicts:
          {'side': 'BUY'|'SELL', 'qty': int}
        """
        return []

    def parameters(self) -> dict:
        return {}
