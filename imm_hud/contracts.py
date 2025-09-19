"""Contracts used by replay and HUD integrations."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ReplayEvent:
    """HUD-friendly representation of a ledger event."""

    timestamp: str
    glyph: str
    clauses: dict[str, Any]
    metrics: dict[str, float]


class HUDOverlayBus:
    """Simple pub/sub bus for HUD overlays."""

    def __init__(self) -> None:
        self._subscribers: list[Callable[[ReplayEvent], None]] = []

    def subscribe(self, callback: Callable[[ReplayEvent], None]) -> None:
        self._subscribers.append(callback)

    def publish(self, event: ReplayEvent) -> None:
        for callback in list(self._subscribers):
            callback(event)
