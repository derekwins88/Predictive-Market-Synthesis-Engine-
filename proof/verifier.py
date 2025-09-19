"""TruthLock ledger verifier."""

from __future__ import annotations

import json
from pathlib import Path

from imm_adapters.truthlock import TruthLockVerifier


def verify_file(path: str) -> dict[str, object]:
    return TruthLockVerifier(Path(path)).verify()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Verify a TruthLock ledger")
    parser.add_argument("ledger", help="Path to the ledger file to verify")
    args = parser.parse_args()

    result = verify_file(args.ledger)
    print(json.dumps(result, indent=2))
