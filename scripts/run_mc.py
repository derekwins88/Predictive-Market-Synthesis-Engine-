# scripts/run_mc.py
from __future__ import annotations
import argparse
import importlib
import json
from pathlib import Path
import pandas as pd
from sim.monte_carlo import run_mc

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bars", required=True, type=Path)
    ap.add_argument("--strategy", required=True, help="e.g. strategies.sentient_spire_v12:SentientSpireV12")
    ap.add_argument("--runs", type=int, default=200)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--price_bps", type=float, default=0.0, help="Gaussian price jitter sigma in bps")
    ap.add_argument("--slippage_ticks", type=float, default=1.0)
    ap.add_argument("--report", required=True, type=Path)
    args = ap.parse_args()

    df = pd.read_csv(args.bars)
    mod, cls = args.strategy.split(":")
    Strat = getattr(importlib.import_module(mod), cls)
    def ctor():
        return Strat()

    summary = run_mc(df, ctor, runs=args.runs, seed=args.seed, price_bps=args.price_bps, slippage_ticks=args.slippage_ticks)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(summary, indent=2))
    print(f"✅ wrote {args.report}")

if __name__ == "__main__":
    main()
