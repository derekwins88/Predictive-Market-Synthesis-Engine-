# NT8 Adapter (IMM Bridge)

This folder contains a NinjaTrader 8 adapter that:
- computes a lightweight entropy proxy (ΔΦ ≈ ATR/Close),
- gates trades by regime (P/INTERMEDIATE/NP),
- emits NDJSON capsules + optional CSV ledger (ProofBridge),
- optionally streams JSONL over TCP to an external harness.

Files:
- BarExportEmitter.cs              — indicator exporter with optional TCP broadcast
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

## BarExportEmitter indicator

`BarExportEmitter` is a low-overhead indicator that writes each completed bar to
CSV and/or NDJSON, with an optional TCP broadcast that streams the same payload
to an external consumer.

### Install

1. In NT8 open **New → NinjaScript Editor**.
2. Create a new indicator and replace its contents with
   `src/nt8-adapter/BarExportEmitter.cs`.
3. Compile.
4. Add `BarExportEmitter` to any chart.

### Parameters

| Group    | Setting                | Notes |
|----------|-----------------------|-------|
| Export   | Format                | CSV / NDJSON / Both written to disk. |
| Export   | Base Folder           | Defaults to `<UserData>/Exports/Bars`. |
| Export   | File Pattern          | Tokens: `{SYMBOL}`, `{DATE:yyyyMMdd}`, `{TF}`, `{EXT}`. |
| Export   | Write Header (CSV)    | Adds CSV headers once per file. |
| Extras   | Include ΔΦ            | Adds ATR/Close entropy proxy + regime tag. |
| Extras   | ATR Period            | Period used for the ATR component. |
| TCP      | TCP Enabled           | Turns on the async broadcaster. |
| TCP      | TCP Host / Port       | Target listener address. |
| TCP      | Reconnect Backoff     | Delay before reconnect attempts. |
| TCP      | Max Queue Size        | Drops oldest when the consumer lags. |
| TCP      | TCP Payload Format    | CSV / NDJSON / Both over the wire. |

### Behavior

- Files roll by date via `{DATE:yyyyMMdd}` in `FilePattern` (change the pattern
  to accumulate into a single file).
- Each completed bar writes exactly one line to CSV/NDJSON and, if TCP is
  enabled, enqueues the same payload to a non-blocking queue processed by a
  background worker.
- The TCP loop keeps the UI thread free, auto-reconnects, and trims the queue if
  the remote listener falls behind.
- The ΔΦ regime matches the IMM bridge conventions: `P`, `INTERMEDIATE`, and
  `NP` bands.
