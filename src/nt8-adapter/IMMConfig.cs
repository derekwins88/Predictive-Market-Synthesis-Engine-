// src/nt8-adapter/IMMConfig.cs
using System;
using System.IO;
using System.Text;
using Newtonsoft.Json;

namespace IMM.NT8
{
    public sealed class IMMConfig
    {
        public string NdjsonPath { get; set; } =
            Path.Combine(NinjaTrader.Core.Globals.UserDataDir, "Capsules", "COG", "Oracle_v8");
        public string LedgerCsvPath { get; set; } =
            Path.Combine(NinjaTrader.Core.Globals.UserDataDir, "Proof", "trade_ledger.csv");
        public bool AlsoWriteCsvLedger { get; set; } = true;

        // Optional socket sink (disabled by default)
        public bool TcpEnabled { get; set; } = false;
        public string TcpHost { get; set; } = "127.0.0.1";
        public int TcpPort { get; set; } = 5757;

        public static IMMConfig LoadOrDefault(string path = null)
        {
            try
            {
                path ??= Path.Combine(NinjaTrader.Core.Globals.UserDataDir, "imm_nt8_config.json");
                if (!File.Exists(path))
                {
                    var def = new IMMConfig();
                    File.WriteAllText(path, JsonConvert.SerializeObject(def, Formatting.Indented));
                    return def;
                }
                var json = File.ReadAllText(path);
                return JsonConvert.DeserializeObject<IMMConfig>(json) ?? new IMMConfig();
            }
            catch { return new IMMConfig(); }
        }
    }
}
