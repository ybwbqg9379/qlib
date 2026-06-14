#!/usr/bin/env python
# [FORK] Multi-seed re-test: is Custom5's edge over the 6-factor handler real or noise?
# (FORK.md §10 Phase 3, follows §9.9.)
#
# WHY: §9.9 found Alpha158Custom5 (drop LOTTERY21) backtested at +15.3%/yr excess vs the
# 6-factor +5.7%, but Rank IC barely moved — so most of the jump is likely top-50
# portfolio variance, amplified by LightGBM's own training randomness (row/feature
# bagging). A single seed can't tell signal from luck. This trains BOTH handlers across
# the SAME set of seeds (paired) and compares the DISTRIBUTION of excess-return-with-cost.
#   - Data prep is deterministic, so each handler's dataset is built once and reused.
#   - Only the LGBModel seed varies per run.
# Verdict logic: report mean +/- std per handler, and the paired diff (Custom5 - 6f) per
# seed. If the paired diff is positive on most seeds and its mean > ~1 std, the edge is
# robust; if it straddles zero, the +15.3% was a lucky draw.
#
# Run:  MLFLOW_ALLOW_FILE_STORE=true .venv/bin/python examples/fork/multiseed_compare.py

import os

import numpy as np
import pandas as pd

import qlib
from _eval import load_cfg, build_dataset, train_predict, backtest_excess

HERE = os.path.dirname(os.path.abspath(__file__))
CFG6 = os.path.join(HERE, "workflow_config_lightgbm_custom_us_massive.yaml")
SEEDS = [0, 1, 2, 7, 13, 21, 42, 99, 123, 2024]  # 10 seeds
HANDLERS = {
    "6factor": "qlib.custom.data.handler.Alpha158Custom",
    "Custom5": "qlib.custom.data.handler.Alpha158Custom5",
}


def main():
    cfg = load_cfg(CFG6)
    qlib.init(**cfg["qlib_init"])
    bt = cfg["port_analysis_config"]["backtest"]

    rows = []
    for hname, hpath in HANDLERS.items():
        dataset = build_dataset(cfg, handler_class=hpath)  # built once per handler, reused across seeds
        for seed in SEEDS:
            _, pred = train_predict(cfg, dataset, seed=seed)
            m = backtest_excess(cfg, pred, bt["start_time"], bt["end_time"])
            rows.append({"handler": hname, "seed": seed, **m})
            print(f"{hname:8s} seed={seed:<5d} excess={m['excess']:+.4f} IR={m['IR']:+.3f} maxDD={m['maxDD']:.3f}")

    df = pd.DataFrame(rows)
    pd.set_option("display.float_format", lambda x: f"{x:0.4f}")
    print("\n=== distribution of excess-return-with-cost (annualized) ===")
    summ = df.groupby("handler")["excess"].agg(["mean", "std", "min", "max"])
    print(summ.to_string())
    print("\n=== per-seed paired diff (Custom5 - 6factor) ===")
    piv = df.pivot(index="seed", columns="handler", values="excess")
    piv["diff"] = piv["Custom5"] - piv["6factor"]
    print(piv.to_string())
    d = piv["diff"]
    wins = (d > 0).sum()
    print(
        f"\nVERDICT: Custom5 beats 6factor on {wins}/{len(d)} seeds | "
        f"mean diff {d.mean():+.4f} +/- {d.std():.4f} | "
        f"{'ROBUST edge' if d.mean() > d.std() and wins >= 0.8*len(d) else 'within noise (single-seed +15% was a lucky draw)'}"
    )


if __name__ == "__main__":
    main()
