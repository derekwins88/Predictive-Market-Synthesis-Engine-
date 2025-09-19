from __future__ import annotations

import numpy as np

from imm_engine import PredictiveSynthesisEngine


def test_predictive_pipeline_runs() -> None:
    engine = PredictiveSynthesisEngine()
    price = np.linspace(100, 101, 64) + np.random.default_rng(1).normal(0, 0.1, 64)
    volume = np.full(64, 1000.0)
    vector = engine.synthesize(price, volume)
    output = engine.predict(vector)
    assert "risk" in output and "exec" in output and output["quality"] >= 0
