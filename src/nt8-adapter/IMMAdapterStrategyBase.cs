// src/nt8-adapter/IMMAdapterStrategyBase.cs
#region Using
using System;
using NinjaTrader.Cbi;
using NinjaTrader.NinjaScript;
using NinjaTrader.NinjaScript.Indicators;
#endregion

namespace IMM.NT8
{
    public abstract class IMMAdapterStrategyBase : Strategy
    {
        // lightweight signals
        protected ATR atr;
        protected double dphi; // entropy proxy
        protected string regime;
        protected IMMBridgeClient bridge;
        protected ProofBridgeLogger proof;

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Calculate = Calculate.OnBarClose;
                BarsRequiredToTrade = 50;
                Name = "IMMAdapterBase";
            }
            else if (State == State.DataLoaded)
            {
                atr = ATR(14);
                var cfg = IMMConfig.LoadOrDefault();
                bridge = new IMMBridgeClient(cfg);
                proof = new ProofBridgeLogger(this, bridge);
            }
        }

        protected EntropyBar MakeEntropyBar()
        {
            dphi = (Close[0] > 0 ? atr[0] / Close[0] : 0.0);
            regime = EntropyMath.RegimeOf(dphi);
            return new EntropyBar
            {
                Symbol = Instrument.MasterInstrument.Name,
                Timestamp = Time[0],
                Open = Open[0], High = High[0], Low = Low[0], Close = Close[0],
                Volume = Volume[0],
                DeltaPhi = dphi,
                Regime = regime,
                CapsuleId = "SESSION⇌" + TradingHours?.Name ?? "RTH"
            };
        }

        protected void LedgerEnter(string name, double price)
        {
            proof.WriteLedger(Time[0], Instrument.MasterInstrument.Name, $"ENTER_{name}", price, dphi, regime, 0.0);
        }

        protected void LedgerExit(string reason, double price, double realized)
        {
            proof.WriteLedger(Time[0], Instrument.MasterInstrument.Name, $"EXIT_{reason}", price, dphi, regime, realized);
        }

        protected override void OnExecutionUpdate(Execution exec, string id, double price, int qty, MarketPosition mp, string orderId, DateTime t)
        {
            if (exec?.Order == null || exec.Order.OrderState != OrderState.Filled) return;

            // If we just flattened, compute realized and log
            if (Position.MarketPosition == MarketPosition.Flat)
            {
                var trades = SystemPerformance.AllTrades;
                double realized = trades.Count > 0 ? trades[trades.Count - 1].ProfitCurrency : 0.0;
                LedgerExit("FLAT", price, realized);
            }
        }

        protected override void OnTermination()
        {
            proof?.Flush();
            base.OnTermination();
        }
    }
}
