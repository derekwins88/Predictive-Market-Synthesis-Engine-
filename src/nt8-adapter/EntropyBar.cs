// src/nt8-adapter/EntropyBar.cs
using System;

namespace IMM.NT8
{
    public struct EntropyBar
    {
        public string Symbol;
        public DateTime Timestamp;
        public double Open, High, Low, Close, Volume;
        public double DeltaPhi;    // entropy proxy (e.g., ATR/Close or your Shannon)
        public string Regime;      // "P" | "INTERMEDIATE" | "NP"
        public string CapsuleId;   // session capsule lineage id
    }

    public static class EntropyMath
    {
        public static string RegimeOf(double dphi) =>
            dphi < 0.045 ? "P" : dphi >= 0.09 ? "NP" : "INTERMEDIATE";
    }
}
