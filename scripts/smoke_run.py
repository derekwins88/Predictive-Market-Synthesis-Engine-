"""Minimal smoke pipeline: CSV → synthesis engine → TruthLock ledger."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

from imm_adapters import TruthLockWriter, stream_csv
from imm_engine import PredictiveSynthesisEngine


def main(csv_path: str) -> None:
    engine = PredictiveSynthesisEngine()
    prices: list[float] = []
    volumes: list[float] = []
    writer = TruthLockWriter(Path("logs/ledger.jsonl"))

    for record in stream_csv(csv_path):
        prices.append(record["close"])
        volumes.append(record["volume"])
        price_slice = np.asarray(prices[-128:], dtype=float)
        volume_slice = np.asarray(volumes[-128:], dtype=float)
        vector = engine.synthesize(price_slice, volume_slice)
        prediction = engine.predict(vector)
        glyph = "StrongBloom_*" if prediction["risk"]["level"] != "high" else "Hermit_Defer"
        decision = "enter" if prediction["exec"]["priority"] == "high" else "observe"
        writer.write(
            {
                "ts": str(record["timestamp"]),
                "glyph": glyph,
                "decision": decision,
                "quality": prediction["quality"],
                "risk_level": prediction["risk"]["level"],
            }
        )

    print("✅ smoke run done. see logs/ledger.jsonl")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python scripts/smoke_run.py tests/data/sample_bars.csv")
        raise SystemExit(2)
    main(sys.argv[1])
