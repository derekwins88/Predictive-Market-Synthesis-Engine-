"""CSV streaming adapter used by smoke tests and integrations."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import pandas as pd


def stream_csv(path: str) -> Iterable[dict[str, Any]]:
    """Yield normalized bar records from ``path``.

    The helper normalizes column names so downstream components always receive the
    canonical schema (timestamp, symbol, open, high, low, close, volume).
    """

    df = pd.read_csv(path)

    rename = {
        "time": "timestamp",
        "datetime": "timestamp",
        "date": "timestamp",
        "sym": "symbol",
    }
    for source, target in rename.items():
        if source in df.columns and target not in df.columns:
            df[target] = df[source]

    required = ["timestamp", "symbol", "open", "high", "low", "close", "volume"]
    missing = [column for column in required if column not in df.columns]
    if missing:
        raise ValueError(f"CSV missing required columns: {missing}")

    timestamps = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    df = (
        df.assign(timestamp=timestamps)
        .dropna(subset=["timestamp"])
        .sort_values("timestamp")
    )

    for _, row in df.iterrows():
        yield {
            "timestamp": row["timestamp"],
            "symbol": row["symbol"],
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
            "volume": float(row["volume"]),
        }
