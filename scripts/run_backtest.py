# scripts/run_backtest.py
from __future__ import annotations
import argparse
import importlib
import json
from pathlib import Path
import pandas as pd
from sim.engine import run_once

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bars", required=True, type=Path, help="CSV with columns: timestamp,open,high,low,close,volume")
    ap.add_argument("--strategy", required=True, help="e.g. strategies.sentient_spire_v12:SentientSpireV12")
    ap.add_argument("--report", required=True, type=Path, help="Output JSON path")
    args = ap.parse_args()

    df = pd.read_csv(args.bars)
    module_name, class_name = args.strategy.split(":")
    Strat = getattr(importlib.import_module(module_name), class_name)
    strat = Strat()

    result = run_once(df, strat)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2))
    print(f"✅ wrote {args.report}")

if __name__ == "__main__":
    main()
