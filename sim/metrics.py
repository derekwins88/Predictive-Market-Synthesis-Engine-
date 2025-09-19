# sim/metrics.py
from __future__ import annotations
import numpy as np
import pandas as pd

def daily_roi_df(equity: pd.Series) -> pd.DataFrame:
    eq = equity.dropna()
    if eq.empty:
        return pd.DataFrame(columns=["date", "roi_pct", "pnl"])
    daily = eq.resample("1D").last().dropna()
    roi = daily.pct_change().fillna(0.0) * 100.0
    pnl = daily.diff().fillna(0.0)
    return pd.DataFrame({"date": daily.index.date, "roi_pct": roi.values, "pnl": pnl.values})

def max_drawdown_pct(equity: pd.Series) -> float:
    eq = equity.dropna()
    if eq.empty:
        return 0.0
    run_max = eq.cummax()
    dd = (eq / run_max - 1.0).min()
    return float(abs(dd) * 100.0)

def sharpe_daily(equity: pd.Series, rf: float = 0.0) -> float:
    ret = equity.pct_change().dropna()
    if ret.std() == 0 or ret.empty:
        return 0.0
    ex = ret - rf / 252.0
    return float(np.sqrt(252) * ex.mean() / ex.std())

def calmar(equity: pd.Series) -> float:
    eq = equity.dropna()
    if len(eq) < 2:
        return 0.0
    total_ret = eq.iloc[-1] / eq.iloc[0] - 1.0
    years = max(1e-9, len(eq) / (252 * 24 * 60))  # crude if minute bars; safe fallback
    cagr = (1.0 + total_ret) ** (1.0 / years) - 1.0 if years > 0 else 0.0
    mdd = max_drawdown_pct(eq) / 100.0
    return 0.0 if mdd == 0 else float(cagr / mdd)

def equity_stats(equity: pd.Series) -> dict:
    daily = daily_roi_df(equity)
    win_rate = float((daily["roi_pct"] > 0).mean()) if not daily.empty else 0.0
    stats = {
        "median_daily_roi_pct": float(daily["roi_pct"].median() if not daily.empty else 0.0),
        "p05_daily_roi_pct": float(np.percentile(daily["roi_pct"], 5) if not daily.empty else 0.0),
        "p95_daily_roi_pct": float(np.percentile(daily["roi_pct"], 95) if not daily.empty else 0.0),
        "max_drawdown_pct": max_drawdown_pct(equity),
        "sharpe": sharpe_daily(equity),
        "calmar": calmar(equity),
        "win_rate": win_rate,
    }
    return stats
