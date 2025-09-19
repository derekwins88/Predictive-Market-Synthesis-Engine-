"""TruthLock ledger utilities."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class TruthLockWriter:
    """Append-only hash chained JSONL writer."""

    path: Path
    _tip: str | None = field(init=False, default=None)

    def __post_init__(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("", encoding="utf-8")
            self._tip = None
            return

        last_line = ""
        with self.path.open("r", encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.rstrip("\n")
                if line.strip():
                    last_line = line
        if last_line:
            self._tip = hashlib.sha256(last_line.encode("utf-8")).hexdigest()
        else:
            self._tip = None

    def write(self, record: dict[str, object]) -> str:
        """Append ``record`` to the ledger and return the new tip hash."""

        payload = {"prev": self._tip or "", **record}
        line = json.dumps(payload, separators=(",", ":"), sort_keys=True)
        tip = hashlib.sha256(line.encode("utf-8")).hexdigest()
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
        self._tip = tip
        return tip

    @property
    def tip(self) -> str | None:
        """Return the most recent hash tip."""

        return self._tip


@dataclass
class TruthLockVerifier:
    """Validate the hash chain stored in a TruthLock ledger."""

    path: Path

    def verify(self) -> dict[str, object]:
        if not self.path.exists():
            return {"ok": True, "lines": 0, "tip": ""}

        previous_hash = ""
        ok = True
        count = 0

        with self.path.open("r", encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.rstrip("\n")
                if not line.strip():
                    continue
                count += 1
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    ok = False
                    break
                if obj.get("prev", "") != previous_hash:
                    ok = False
                    break
                previous_hash = hashlib.sha256(line.encode("utf-8")).hexdigest()

        return {"ok": ok, "lines": count, "tip": previous_hash}
