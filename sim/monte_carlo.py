# sim/monte_carlo.py
from __future__ import annotations
from typing import Callable
import numpy as np
import pandas as pd
from .engine import run_once

def perturb_bars(bars: pd.DataFrame, rng: np.random.Generator, price_bps: float = 0.0) -> pd.DataFrame:
    if price_bps <= 0:
        return bars
    jitter = 1.0 + rng.normal(0.0, price_bps / 10_000.0, size=len(bars))
    df = bars.copy()
    for col in ("open", "high", "low", "close"):
        df[col] = (df[col].to_numpy() * jitter).astype(float)
    return df

def run_mc(
    bars: pd.DataFrame,
    strategy_ctor: Callable[[], object],
    runs: int = 200,
    seed: int = 42,
    price_bps: float = 0.0,
    slippage_ticks: float = 1.0,
) -> dict:
    rng = np.random.default_rng(seed)
    summaries = []
    for _ in range(runs):
        dfp = perturb_bars(bars, rng, price_bps=price_bps)
        strat = strategy_ctor()
        res = run_once(
            dfp,
            strat,
            slippage_ticks=slippage_ticks * max(0.5, rng.normal(1.0, 0.1)),
        )
        summaries.append(res["summary"])

    # Aggregate: median/p05/p95 daily ROI from summaries that carry per-day stats
    med = np.median([s["median_daily_roi_pct"] for s in summaries])
    p05 = np.percentile([s["median_daily_roi_pct"] for s in summaries], 5)
    p95 = np.percentile([s["median_daily_roi_pct"] for s in summaries], 95)
    max_dd = float(np.max([s["max_drawdown_pct"] for s in summaries]))
    win = float(np.mean([s["win_rate"] for s in summaries]))
    calmar = float(np.median([s["calmar"] for s in summaries]))

    return {
        "summary": {
            "median_daily_roi_pct": float(med),
            "p05_daily_roi_pct": float(p05),
            "p95_daily_roi_pct": float(p95),
            "max_drawdown_pct": max_dd,
            "win_rate": win,
            "calmar": calmar,
            "runs": runs,
        }
    }
