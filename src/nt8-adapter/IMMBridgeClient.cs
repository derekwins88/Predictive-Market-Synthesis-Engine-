// src/nt8-adapter/IMMBridgeClient.cs
using System;
using System.IO;
using System.Net.Sockets;
using System.Text;
using Newtonsoft.Json;

namespace IMM.NT8
{
    public interface IBridgeSink
    {
        void WriteJsonLine(object o);
        void WriteCsvLine(string csv);
        void Flush();
    }

    public sealed class FileSink : IBridgeSink
    {
        private readonly string ndjsonFile;
        private readonly string csvFile;
        private readonly bool writeCsv;

        public FileSink(string ndjsonDir, string csvPath, bool writeCsvLedger)
        {
            Directory.CreateDirectory(ndjsonDir);
            ndjsonFile = Path.Combine(ndjsonDir, $"cog_{DateTime.UtcNow:yyyyMMdd}.ndjson");
            csvFile = csvPath;
            writeCsv = writeCsvLedger;

            if (writeCsv && !File.Exists(csvFile))
                File.WriteAllText(csvFile, "timestamp,capsule_id,action,price,delta_phi,regime,realized\n");
        }

        public void WriteJsonLine(object o)
        {
            var line = JsonConvert.SerializeObject(o);
            File.AppendAllText(ndjsonFile, line + "\n");
        }

        public void WriteCsvLine(string csv)
        {
            if (!writeCsv) return;
            File.AppendAllText(csvFile, csv + "\n");
        }

        public void Flush() { /* file appends are durable per write */ }
    }

    public sealed class TcpSink : IBridgeSink
    {
        private readonly FileSink fallback;
        private readonly bool enabled;
        private TcpClient client;
        private NetworkStream stream;

        public TcpSink(FileSink fallback, bool enable, string host, int port)
        {
            this.fallback = fallback;
            enabled = enable;
            if (!enabled) return;
            try
            {
                client = new TcpClient();
                client.Connect(host, port);
                stream = client.GetStream();
            }
            catch { enabled = false; /* fall back to file only */ }
        }

        public void WriteJsonLine(object o)
        {
            var line = JsonConvert.SerializeObject(o) + "\n";
            if (enabled && stream != null && stream.CanWrite)
            {
                var bytes = Encoding.UTF8.GetBytes(line);
                try { stream.Write(bytes, 0, bytes.Length); }
                catch { /* drop to file */ fallback.WriteJsonLine(o); }
            }
            else fallback.WriteJsonLine(o);
        }

        public void WriteCsvLine(string csv)
        {
            var line = csv + "\n";
            if (enabled && stream != null && stream.CanWrite)
            {
                var bytes = Encoding.UTF8.GetBytes(line);
                try { stream.Write(bytes, 0, bytes.Length); }
                catch { fallback.WriteCsvLine(csv); }
            }
            else fallback.WriteCsvLine(csv);
        }

        public void Flush()
        {
            try { stream?.Flush(); } catch { }
        }
    }

    public sealed class IMMBridgeClient
    {
        private readonly IBridgeSink sink;
        public IMMBridgeClient(IMMConfig cfg)
        {
            var fileSink = new FileSink(cfg.NdjsonPath, cfg.LedgerCsvPath, cfg.AlsoWriteCsvLedger);
            sink = cfg.TcpEnabled ? new TcpSink(fileSink, true, cfg.TcpHost, cfg.TcpPort) : (IBridgeSink)fileSink;
        }

        public void EmitCapsule(dynamic capsule) => sink.WriteJsonLine(capsule);
        public void EmitLedgerCsv(string csvLine) => sink.WriteCsvLine(csvLine);
        public void Flush() => sink.Flush();
    }
}
