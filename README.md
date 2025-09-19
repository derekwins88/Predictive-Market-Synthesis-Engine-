# IMM Synthesis Engine

A unified market cognition stack:
- **engine/**: predictive synthesis (entropy × topology × quantum-state mock)
- **adapters/**: bridges to NinjaTrader, CSV feeds, NDJSON capsules
- **hud/**: replay + trauma-mode overlays
- **proof/**: TruthLock/Clause verifiers, Lean 4 stubs, hash-chain tools
- **arena/**: metaphysical capsules (Glyph Arena) for symbolic experiments
- **tests/**: smoke tests + regression

> Motto: *Echo the glyph; let proof carry the light.*

## Quick start
```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .
pytest -q
python scripts/smoke_run.py tests/data/sample_bars.csv
```

Architecture (high level)

    +-------------------+     +----------------------+     +------------------+
    |   data adapters   | --> |  synthesis engine    | --> | execution plan   |
    | (csv, NT bridge)  |     | (entropy, topology,  |     | (risk, sizing,   |
    |                   |     |  quantum mock, GW)   |     |  timing)         |
    +-------------------+     +----------------------+     +------------------+
                \                     |       \                      |
                 \                    |        \                     v
                  \                   |         +----------> proof/ledger & HUD

Packages
- `imm_engine`: core synthesis + APIs
- `imm_adapters`: I/O, NT bridge, capsule emitters
- `imm_hud`: replay render interfaces
- `imm_proof`: hash-chain, CSV/JSONL verifiers

See `ROADMAP.md` for staged milestones.
