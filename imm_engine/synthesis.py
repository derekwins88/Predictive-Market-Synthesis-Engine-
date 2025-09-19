"""Predictive synthesis engine primitives."""

from __future__ import annotations

import time
from collections import deque
from collections.abc import Mapping, MutableMapping
from dataclasses import dataclass
from enum import Enum
from typing import Any

import numpy as np


class IntelligenceLevel(str, Enum):
    """Approximate level of synthesis capability."""

    REACTIVE = "reactive"
    PREDICTIVE = "predictive"
    ANTICIPATORY = "anticipatory"
    VISIONARY = "visionary"


@dataclass
class SynthesisVector:
    """Container for engine state and derived projections."""

    entropy_signature: np.ndarray
    topology_embedding: np.ndarray
    quantum_state: np.ndarray
    focus: str
    conf: float
    ts: float

    def predictive_power(self) -> float:
        """Return an aggregate quality score."""

        entropy_component = 1.0 - float(np.std(self.entropy_signature))
        topology_component = float(np.clip(np.mean(self.topology_embedding), -1.0, 1.0))
        coherence_component = float(np.real(np.vdot(self.quantum_state, self.quantum_state)))
        return (
            0.4 * entropy_component
            + 0.3 * topology_component
            + 0.2 * coherence_component
            + 0.1 * self.conf
        )


class PredictiveSynthesisEngine:
    """Composable predictive engine with lightweight deterministic stubs."""

    def __init__(self, timeframes: Mapping[str, int] | None = None) -> None:
        default_timeframes: dict[str, int] = {
            "micro": 60,
            "short": 300,
            "medium": 1800,
            "macro": 86_400,
        }
        self.timeframes: MutableMapping[str, int] = dict(timeframes or default_timeframes)
        self._ordered_timeframes = list(self.timeframes.items())
        self.level = IntelligenceLevel.REACTIVE
        self.hist: deque[SynthesisVector] = deque(maxlen=10_000)
        self._acc = 0.65

    # ---- core -----------------------------------------------------------------
    def synthesize(self, price: np.ndarray, volume: np.ndarray) -> SynthesisVector:
        price = np.asarray(price, dtype=float)
        volume = np.asarray(volume, dtype=float)
        entropy_signature = self._entropy_signature(price)
        topology_embedding = self._topology_embedding(price, volume)
        quantum_state = self._quantum_state(8)
        focus = self._focus()
        conf = self._confidence(entropy_signature, topology_embedding, quantum_state)
        vector = SynthesisVector(
            entropy_signature=entropy_signature,
            topology_embedding=topology_embedding,
            quantum_state=quantum_state,
            focus=focus,
            conf=conf,
            ts=time.time(),
        )
        self.hist.append(vector)
        return vector

    def predict(self, vector: SynthesisVector) -> dict[str, Any]:
        predictions: dict[str, dict[str, float]] = {}
        for idx, (name, seconds) in enumerate(self._ordered_timeframes):
            predictions[name] = self._predict_horizon(vector, idx, seconds)
        confidence_values = [prediction["confidence"] for prediction in predictions.values()] or [
            vector.conf
        ]
        meta = 1.0 - float(np.std(confidence_values))
        self._update_level(vector, meta)
        regime = self._regime(vector)
        risk = self._risk(vector, predictions)
        execution = self._execution(vector, predictions, risk)
        return {
            "ts": vector.ts,
            "level": self.level.value,
            "preds": predictions,
            "meta": meta,
            "regime": regime,
            "risk": risk,
            "exec": execution,
            "quality": vector.predictive_power(),
        }

    # ---- feature extractors ---------------------------------------------------
    def _entropy_signature(self, price: np.ndarray) -> np.ndarray:
        output = np.zeros(len(self._ordered_timeframes), dtype=float)
        if price.size < 4:
            return output
        window = price[-64:] if price.size >= 64 else price
        log_prices = np.log(np.maximum(window, 1e-9))
        returns = np.diff(log_prices)
        if returns.size == 0:
            return output
        mu = float(np.mean(returns))
        sigma = float(np.std(returns))
        baseline = sigma / abs(mu) if abs(mu) > 1e-9 else sigma
        for index in range(len(output)):
            output[index] = float(np.clip(baseline * (1.0 + 0.1 * index), 0.0, 0.5))
        return output

    def _topology_embedding(
        self, price: np.ndarray, volume: np.ndarray
    ) -> np.ndarray:  # noqa: ARG002
        rng = np.random.default_rng(42 + (price.size % 997))
        return rng.normal(0.0, 0.1, 64)

    def _quantum_state(self, n: int) -> np.ndarray:
        rng = np.random.default_rng(7 + n)
        amplitude = rng.uniform(0.0, 1.0, n)
        phase = rng.uniform(0.0, 2.0 * np.pi, n)
        state = amplitude * np.exp(1j * phase)
        norm = np.linalg.norm(state)
        if norm == 0:
            return np.zeros(n, dtype=complex)
        return state / norm

    def _focus(self) -> str:
        options = [
            "trend_following",
            "mean_reversion",
            "risk",
            "momentum",
            "volatility",
        ]
        index = int(time.time()) % len(options)
        return options[index]

    def _confidence(self, entropy: np.ndarray, topology: np.ndarray, quantum: np.ndarray) -> float:
        entropy_term = 1.0 / (1.0 + float(np.var(entropy)) + 1e-9)
        topology_term = float(np.clip(np.linalg.norm(topology) / 10.0, 0.0, 1.0))
        quantum_term = float(np.real(np.vdot(quantum, quantum)))
        return 0.3 * entropy_term + 0.3 * topology_term + 0.2 * quantum_term + 0.2 * self._acc

    # ---- projections ----------------------------------------------------------
    def _predict_horizon(
        self, vector: SynthesisVector, index: int, seconds: int
    ) -> dict[str, float]:
        if index < vector.entropy_signature.size:
            entropy_component = float(vector.entropy_signature[index])
        else:
            entropy_component = 0.0
        direction_probability = float(np.clip(0.5 + (entropy_component - 0.05) * 2.0, 0.1, 0.9))
        magnitude = entropy_component * 100.0
        return {
            "direction_probability": direction_probability,
            "magnitude": magnitude,
            "confidence": vector.conf,
            "horizon_seconds": float(seconds),
        }

    def _regime(self, vector: SynthesisVector) -> dict[str, float | str]:
        if vector.entropy_signature.size > 1:
            x = np.arange(vector.entropy_signature.size, dtype=float)
            slope = float(np.polyfit(x, vector.entropy_signature, 1)[0])
        else:
            slope = 0.0
        mean_entropy = float(np.mean(vector.entropy_signature))
        if mean_entropy > 0.1:
            current = "high_volatility"
        elif slope > 0.01:
            current = "trending"
        else:
            current = "normal"
        return {
            "current": current,
            "confidence": vector.conf,
            "trend": slope,
            "mean": mean_entropy,
        }

    def _risk(
        self,
        vector: SynthesisVector,
        predictions: dict[str, dict[str, float]],
    ) -> dict[str, float | str]:
        entropy_risk = float(np.mean(vector.entropy_signature)) * 2.0
        topology_risk = float(np.std(vector.topology_embedding)) * 5.0
        if predictions:
            uncertainty = float(
                np.mean([1.0 - pred["confidence"] for pred in predictions.values()])
            )
        else:
            uncertainty = 0.0
        quantum_risk = 1.0 - float(np.real(np.vdot(vector.quantum_state, vector.quantum_state)))
        total = entropy_risk + topology_risk + uncertainty + quantum_risk
        if total > 2.0:
            level = "high"
        elif total > 1.0:
            level = "medium"
        else:
            level = "low"
        return {
            "total": total,
            "entropy": entropy_risk,
            "topology": topology_risk,
            "uncertainty": uncertainty,
            "quantum": quantum_risk,
            "level": level,
        }

    def _execution(
        self,
        vector: SynthesisVector,
        predictions: dict[str, dict[str, float]],
        risk: dict[str, float | str],
    ) -> dict[str, float | str]:
        risk_total = float(risk.get("total", 0.0))
        adj = max(0.1, 1.0 - risk_total / 4.0)
        short_prob = float(predictions.get("short", {}).get("direction_probability", 0.5))
        medium_prob = float(predictions.get("medium", {}).get("direction_probability", 0.5))
        agreement = 1.0 - abs(short_prob - medium_prob)
        conf_mult = 1.0 + 0.5 * agreement
        size = adj * conf_mult
        micro_confidence = float(predictions.get("micro", {}).get("confidence", 0.0))
        entry = "immediate" if micro_confidence > 0.7 else "gradual"
        stop_mult = 1.0 + float(np.mean(vector.entropy_signature)) * 10.0
        priority = "high" if vector.conf > 0.8 else "normal"
        return {
            "size": size,
            "adj": adj,
            "conf_mult": conf_mult,
            "entry": entry,
            "stop_mult": stop_mult,
            "priority": priority,
        }

    def _update_level(self, vector: SynthesisVector, meta: float) -> None:
        if meta > 0.8 and vector.conf > 0.8:
            self.level = IntelligenceLevel.VISIONARY
        elif meta > 0.6:
            self.level = IntelligenceLevel.ANTICIPATORY
        elif meta > 0.4:
            self.level = IntelligenceLevel.PREDICTIVE
        else:
            self.level = IntelligenceLevel.REACTIVE
