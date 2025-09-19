// src/nt8-adapter/EntropyEchoDriftSentinel_Adapter.cs
#region Using
using System;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using NinjaTrader.NinjaScript.Indicators;
#endregion

namespace IMM.NT8
{
    public class EntropyEchoDriftSentinel_Adapter : IMMAdapterStrategyBase
    {
        [NinjaScriptProperty, Range(0.5, 0.95)]
        [Display(Name="Base Conviction Threshold", GroupName="Conviction", Order=1)]
        public double BaseConvictionThreshold { get; set; } = 0.75;

        private EMA emaFast, emaSlow;
        private RSI rsi;

        protected override void OnStateChange()
        {
            base.OnStateChange();
            if (State == State.DataLoaded)
            {
                emaFast = EMA(10);
                emaSlow = EMA(40);
                rsi = RSI(14, 3);
                AddChartIndicator(emaFast);
                AddChartIndicator(emaSlow);
            }
        }

        protected override void OnBarUpdate()
        {
            if (CurrentBar < BarsRequiredToTrade) return;

            // Build entropy bar & quick features
            var eb = MakeEntropyBar();
            bool trendAlignedLong = emaFast[0] > emaSlow[0];
            bool trendAlignedShort = emaFast[0] < emaSlow[0];
            double rsiNeutrality = 1.0 - Math.Min(1.0, Math.Abs(rsi[0] - 50) / 50.0);
            double dynConv = 0.35 * rsiNeutrality + 0.65 * Math.Min(1.0, Math.Abs(emaFast[0] - emaSlow[0]) / (atr[0] * 2.0));

            // regime gate (skip NP)
            bool regimeOK = eb.Regime != "NP";

            // decide
            string glyph = "Hermit_Defer";
            string decision = "Hold";

            if (regimeOK && dynConv >= BaseConvictionThreshold)
            {
                if (trendAlignedLong && Position.MarketPosition == MarketPosition.Flat)
                {
                    glyph = "StrongBloom_*";
                    decision = "EnterLong";
                    EnterLong(1, "EEDS_Long");
                    LedgerEnter("LONG", Close[0]);
                }
                else if (trendAlignedShort && Position.MarketPosition == MarketPosition.Flat)
                {
                    glyph = "StrongBloom_*";
                    decision = "EnterShort";
                    EnterShort(1, "EEDS_Short");
                    LedgerEnter("SHORT", Close[0]);
                }
            }

            // emit capsule line once per bar
            proof.WriteCapsule(eb, glyph, decision, dynConv, regimeOK, trendAlignedLong || trendAlignedShort);

            // simple protective exit if RSI flips hard
            if (Position.MarketPosition == MarketPosition.Long && rsi[0] < 45)
                ExitLong("RSIFlipExit", "EEDS_Long");
            if (Position.MarketPosition == MarketPosition.Short && rsi[0] > 55)
                ExitShort("RSIFlipExit", "EEDS_Short");

            if (CurrentBar % 50 == 0) proof.Flush();
        }
    }
}
