// src/nt8-adapter/ProofBridgeLogger.cs
using System;
using System.Linq;
using NinjaTrader.NinjaScript;

namespace IMM.NT8
{
    public sealed class ProofBridgeLogger
    {
        private readonly Strategy strat;
        private readonly IMMBridgeClient client;

        public ProofBridgeLogger(Strategy s, IMMBridgeClient c) { strat = s; client = c; }

        public void WriteCapsule(EntropyBar eb, string glyph, string decision, double dynConviction, bool regimeOK, bool trendAligned)
        {
            var capsule = new
            {
                capsule_id = "IMM⇌COGNITION⇌EchoThread_Oracle_v8.v3.7",
                emitted_at = eb.Timestamp.ToString("o"),
                symbol = eb.Symbol,
                glyph,
                decision,
                regime_ok = regimeOK,
                trend_aligned = trendAligned,
                fractal_vol = eb.DeltaPhi,
                dynamic_conviction = dynConviction,
                last_trade_pnl = strat.SystemPerformance.AllTrades.Count > 0
                    ? strat.SystemPerformance.AllTrades.Last().ProfitCurrency : 0.0
            };
            client.EmitCapsule(capsule);
        }

        public void WriteLedger(DateTime ts, string sym, string action, double price, double dphi, string regime, double realized)
        {
            string id = $"TRADE⇌{sym}⇌{new DateTimeOffset(ts).ToUnixTimeSeconds()}";
            string line = $"{ts:O},{id},{action},{price},{dphi},{regime},{realized}";
            client.EmitLedgerCsv(line);
        }

        public void Flush() => client.Flush();
    }
}
