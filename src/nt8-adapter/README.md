# NT8 Adapter (IMM Bridge)

This folder contains a NinjaTrader 8 adapter that:
- computes a lightweight entropy proxy (ΔΦ ≈ ATR/Close),
- gates trades by regime (P/INTERMEDIATE/NP),
- emits NDJSON capsules + optional CSV ledger (ProofBridge),
- optionally streams JSONL over TCP to an external harness.

Files:
- IMMConfig.cs               — loads/writes adapter config
- IMMBridgeClient.cs         — file/tcp sinks
- EntropyBar.cs              — ΔΦ struct + regime map
- ProofBridgeLogger.cs       — capsule + ledger writers
- IMMAdapterStrategyBase.cs  — base class with logging & ledger hooks
- EntropyEchoDriftSentinel_Adapter.cs — your strategy wired to the bridge

Deploy:
1) Open NT8 > New > NinjaScript Editor.
2) Create a new folder `IMM.NT8` (namespace).
3) Add each `.cs` file there and compile.
4) In a chart, add `EntropyEchoDriftSentinel_Adapter` as a strategy.
5) A config file `imm_nt8_config.json` will be created in your NT8 UserDataDir.
6) Outputs:
   - NDJSON:  `<UserData>/Capsules/COG/Oracle_v8/cog_YYYYMMDD.ndjson`
   - CSV:     `<UserData>/Proof/trade_ledger.csv`
7) For TCP streaming, set `"TcpEnabled": true` in the config and run your external listener.

Notes:
- Replace the ΔΦ proxy with your Shannon/bucketed entropy when ready.
- The adapter is strategy-agnostic; inherit from `IMMAdapterStrategyBase` to wire other builds.
