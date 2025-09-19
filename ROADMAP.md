# Roadmap

## Milestone A: Foundational (this drop)
- engine: `PredictiveSynthesisEngine` (v0.1)
- adapters: CSV runner, NDJSON `TruthLockWriter`
- proof: hash-chain verifier (Python), Lean stub
- hud: replay contract + stub renderer
- CI: lint, tests, smoke run

## Milestone B: Execution Surface
- NT8 binding: `OnExecutionUpdate` → JSONL + hash chain
- EchoTruthReflex cooldown + sentinel gates
- ReplayHUD WPF (live), mini timeline bars

## Milestone C: Arena & Formalization
- Glyph Arena capsules (entities, phases, rules)
- `ClauseMutationLogger` + verifier
- Formal obligations suite (Lean 4: obligations as theorems)
