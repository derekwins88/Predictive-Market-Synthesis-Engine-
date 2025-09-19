#region Using declarations
using System;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.Globalization;
using System.IO;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using System.Collections.Concurrent;
using NinjaTrader.Gui.Tools;
using NinjaTrader.NinjaScript;
using NinjaTrader.NinjaScript.Indicators;
#endregion

// Place in: NinjaTrader.NinjaScript.Indicators
namespace NinjaTrader.NinjaScript.Indicators
{
    public class BarExportEmitter : Indicator
    {
        // ---------------- Params ----------------
        public enum ExportFormat { CSV, NDJSON, Both }

        [NinjaScriptProperty]
        [Display(Name = "Format", GroupName = "Export", Order = 0)]
        public ExportFormat Format { get; set; } = ExportFormat.CSV;

        [NinjaScriptProperty]
        [Display(Name = "Base Folder", GroupName = "Export", Order = 1)]
        public string BaseFolder { get; set; } = null;

        [NinjaScriptProperty]
        [Display(Name = "File Pattern", GroupName = "Export", Order = 2,
                 Description = "Tokens: {SYMBOL} {DATE:yyyyMMdd} {TF} {EXT}")]
        public string FilePattern { get; set; } = "bars_{SYMBOL}_{DATE:yyyyMMdd}.{EXT}";

        [NinjaScriptProperty]
        [Display(Name = "Write Header (CSV)", GroupName = "Export", Order = 3)]
        public bool WriteHeader { get; set; } = true;

        [NinjaScriptProperty]
        [Display(Name = "Include ΔΦ (ATR/Close)", GroupName = "Extras", Order = 10)]
        public bool IncludeDeltaPhi { get; set; } = true;

        [NinjaScriptProperty, Range(2, 200)]
        [Display(Name = "ATR Period (for ΔΦ)", GroupName = "Extras", Order = 11)]
        public int AtrPeriod { get; set; } = 14;

        // -------- TCP Broadcast --------
        [NinjaScriptProperty]
        [Display(Name = "TCP Enabled", GroupName = "TCP", Order = 20)]
        public bool TcpEnabled { get; set; } = false;

        [NinjaScriptProperty]
        [Display(Name = "TCP Host", GroupName = "TCP", Order = 21)]
        public string TcpHost { get; set; } = "127.0.0.1";

        [NinjaScriptProperty, Range(1, 65535)]
        [Display(Name = "TCP Port", GroupName = "TCP", Order = 22)]
        public int TcpPort { get; set; } = 9099;

        [NinjaScriptProperty, Range(100, 600000)]
        [Display(Name = "Reconnect Backoff (ms)", GroupName = "TCP", Order = 23)]
        public int TcpReconnectMs { get; set; } = 2000;

        [NinjaScriptProperty, Range(100, 100000)]
        [Display(Name = "Max Queue Size (lines)", GroupName = "TCP", Order = 24)]
        public int TcpMaxQueue { get; set; } = 5000;

        [NinjaScriptProperty]
        [Display(Name = "TCP Payload Format", GroupName = "TCP", Order = 25,
                 Description = "CSV or NDJSON over the wire")]
        public ExportFormat TcpPayloadFormat { get; set; } = ExportFormat.NDJSON;

        // ---------------- Internals ----------------
        private ATR atr;
        private string outDir;
        private string csvPath;
        private string ndjsonPath;
        private bool headerEnsured;
        private CultureInfo inv = CultureInfo.InvariantCulture;

        // TCP internals
        private CancellationTokenSource tcpCts;
        private Task tcpWorker;
        private TcpClient tcpClient;
        private NetworkStream tcpStream;
        private readonly ConcurrentQueue<string> sendQueue = new ConcurrentQueue<string>();
        private volatile bool tcpRunning;

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Name = "BarExportEmitter";
                Description = "Exports each completed bar to CSV/NDJSON and (optionally) broadcasts over TCP.";
                Calculate = Calculate.OnBarClose;
                IsOverlay = true;
                IsSuspendedWhileInactive = true;
            }
            else if (State == State.Configure)
            {
                // nothing
            }
            else if (State == State.DataLoaded)
            {
                if (IncludeDeltaPhi)
                    atr = ATR(AtrPeriod);

                outDir = BaseFolder;
                if (string.IsNullOrWhiteSpace(outDir))
                    outDir = Path.Combine(NinjaTrader.Core.Globals.UserDataDir, "Exports", "Bars");
                Directory.CreateDirectory(outDir);

                headerEnsured = false;
                BuildPaths();

                // Start TCP if enabled
                if (TcpEnabled)
                    StartTcp();
            }
            else if (State == State.Terminated)
            {
                StopTcp();
            }
        }

        private void BuildPaths()
        {
            string symbol = Instrument?.MasterInstrument?.Name ?? "UNKNOWN";
            string tf = BarsPeriod.BarsPeriodType + "_" + BarsPeriod.Value;
            string dateToken = (CurrentBar >= 0 ? Time[0].Date : DateTime.Now.Date).ToString("yyyyMMdd", inv);

            string csvPattern = FilePattern.Replace("{SYMBOL}", symbol)
                                           .Replace("{TF}", tf)
                                           .Replace("{DATE:yyyyMMdd}", dateToken)
                                           .Replace("{EXT}", "csv");
            csvPath = Path.Combine(outDir, csvPattern);

            string ndjPattern = FilePattern.Replace("{SYMBOL}", symbol)
                                           .Replace("{TF}", tf)
                                           .Replace("{DATE:yyyyMMdd}", dateToken)
                                           .Replace("{EXT}", "ndjson");
            ndjsonPath = Path.Combine(outDir, ndjPattern);

            headerEnsured = false;
        }

        protected override void OnBarUpdate()
        {
            if (CurrentBar < 1) return;

            // Rebuild (new day creates new file names)
            if (!File.Exists(csvPath) || !File.Exists(ndjsonPath))
                BuildPaths();

            if (Format == ExportFormat.CSV || Format == ExportFormat.Both)
                EnsureHeader();

            var ts = Time[0].ToUniversalTime().ToString("o", inv);
            string symbol = Instrument?.MasterInstrument?.Name ?? "UNKNOWN";

            double dphi = 0.0;
            string regime = "NA";
            if (IncludeDeltaPhi)
            {
                dphi = (Close[0] != 0.0 ? (atr[0] / Close[0]) : 0.0);
                regime = RegimeOf(dphi);
            }

            // Compose CSV & NDJSON
            string csvLine = ComposeCsv(ts, symbol, dphi, regime);
            string ndjLine = ComposeNdjson(ts, symbol, dphi, regime);

            // File outputs
            if (Format == ExportFormat.CSV || Format == ExportFormat.Both)
                SafeAppend(csvPath, csvLine);
            if (Format == ExportFormat.NDJSON || Format == ExportFormat.Both)
                SafeAppend(ndjsonPath, ndjLine);

            // TCP broadcast (non-blocking enqueue)
            if (TcpEnabled && tcpRunning)
            {
                switch (TcpPayloadFormat)
                {
                    case ExportFormat.CSV:
                        EnqueueTcp(csvLine);
                        break;
                    case ExportFormat.NDJSON:
                        EnqueueTcp(ndjLine);
                        break;
                    case ExportFormat.Both:
                        EnqueueTcp(csvLine);
                        EnqueueTcp(ndjLine);
                        break;
                }
            }
        }

        // -------- CSV / JSON builders --------
        private string ComposeCsv(string ts, string symbol, double dphi, string regime)
        {
            // timestamp,symbol,open,high,low,close,volume,delta_phi,regime
            return string.Join(",",
                ts,
                symbol,
                Open[0].ToString(inv),
                High[0].ToString(inv),
                Low[0].ToString(inv),
                Close[0].ToString(inv),
                Volume[0].ToString(inv),
                IncludeDeltaPhi ? dphi.ToString(inv) : "",
                IncludeDeltaPhi ? regime : ""
            );
        }

        private string ComposeNdjson(string ts, string symbol, double dphi, string regime)
        {
            return "{"
                 + $"\"timestamp\":\"{ts}\"," 
                 + $"\"symbol\":\"{Escape(symbol)}\"," 
                 + $"\"open\":{Open[0].ToString(inv)},"
                 + $"\"high\":{High[0].ToString(inv)},"
                 + $"\"low\":{Low[0].ToString(inv)},"
                 + $"\"close\":{Close[0].ToString(inv)},"
                 + $"\"volume\":{Volume[0].ToString(inv)}"
                 + (IncludeDeltaPhi ? $",\"delta_phi\":{dphi.ToString(inv)},\"regime\":\"{regime}\"" : "")
                 + "}";
        }

        // -------- File helpers --------
        private void EnsureHeader()
        {
            if (!WriteHeader || headerEnsured) return;
            try
            {
                if (!File.Exists(csvPath))
                {
                    Directory.CreateDirectory(Path.GetDirectoryName(csvPath));
                    var header = "timestamp,symbol,open,high,low,close,volume";
                    if (IncludeDeltaPhi) header += ",delta_phi,regime";
                    File.AppendAllText(csvPath, header + Environment.NewLine);
                }
                headerEnsured = true;
            }
            catch { /* non-fatal */ }
        }

        private static void SafeAppend(string path, string line)
        {
            try
            {
                Directory.CreateDirectory(Path.GetDirectoryName(path));
                File.AppendAllText(path, line + Environment.NewLine);
            }
            catch
            {
                try
                {
                    var alt = Path.Combine(Path.GetDirectoryName(path) ?? "",
                        Path.GetFileNameWithoutExtension(path) + "_alt" + Path.GetExtension(path));
                    File.AppendAllText(alt, line + Environment.NewLine);
                }
                catch { }
            }
        }

        private static string RegimeOf(double dphi)
        {
            if (dphi < 0.045) return "P";
            if (dphi >= 0.09) return "NP";
            return "INTERMEDIATE";
        }

        private static string Escape(string s) =>
            (s ?? "").Replace("\\", "\\\\").Replace("\"", "\\\"");

        // -------- TCP subsystem --------
        private void StartTcp()
        {
            StopTcp(); // safety
            tcpCts = new CancellationTokenSource();
            tcpRunning = true;
            tcpWorker = Task.Run(() => TcpLoop(tcpCts.Token));
        }

        private void StopTcp()
        {
            tcpRunning = false;
            try { tcpCts?.Cancel(); } catch { }
            try { tcpStream?.Dispose(); } catch { }
            try { tcpClient?.Close(); } catch { }
            tcpStream = null;
            tcpClient = null;
            tcpWorker = null;
            tcpCts = null;
            // drain quietly
            while (sendQueue.TryDequeue(out _)) { }
        }

        private void EnqueueTcp(string line)
        {
            if (sendQueue.Count >= TcpMaxQueue)
            {
                // Drop oldest — keep freshest data flowing
                sendQueue.TryDequeue(out _);
            }
            sendQueue.Enqueue(line);
        }

        private void TcpLoop(CancellationToken ct)
        {
            byte[] newline = Encoding.UTF8.GetBytes("\n");
            while (!ct.IsCancellationRequested)
            {
                try
                {
                    if (tcpClient == null || !tcpClient.Connected)
                    {
                        tcpClient = new TcpClient();
                        var connectTask = tcpClient.ConnectAsync(TcpHost, TcpPort);
                        connectTask.Wait(ct);
                        tcpStream = tcpClient.GetStream();
                    }

                    // send loop
                    while (!ct.IsCancellationRequested && tcpClient.Connected)
                    {
                        if (!sendQueue.TryDequeue(out var msg))
                        {
                            Thread.Sleep(5);
                            continue;
                        }

                        var bytes = Encoding.UTF8.GetBytes(msg);
                        tcpStream.Write(bytes, 0, bytes.Length);
                        tcpStream.Write(newline, 0, newline.Length);
                        tcpStream.Flush();
                    }
                }
                catch
                {
                    try { tcpStream?.Dispose(); } catch { }
                    try { tcpClient?.Close(); } catch { }
                    tcpStream = null;
                    tcpClient = null;

                    // backoff
                    int delay = Math.Max(100, TcpReconnectMs);
                    var until = DateTime.UtcNow.AddMilliseconds(delay);
                    while (DateTime.UtcNow < until && !ct.IsCancellationRequested)
                        Thread.Sleep(25);
                }
            }
        }
    }
}
