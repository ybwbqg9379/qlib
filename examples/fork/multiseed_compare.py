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

import numpy as np
import pandas as pd
import yaml

import qlib
from qlib.utils import init_instance_by_config
from qlib.contrib.evaluate import backtest_daily, risk_analysis

import os

HERE = os.path.dirname(os.path.abspath(__file__))
CFG6 = os.path.join(HERE, "workflow_config_lightgbm_custom_us_massive.yaml")
SEEDS = [0, 1, 2, 7, 13, 21, 42, 99, 123, 2024]  # 10 seeds
HANDLERS = {
    "6factor": "qlib.custom.data.handler.Alpha158Custom",
    "Custom5": "qlib.custom.data.handler.Alpha158Custom5",
}


def excess_with_cost(report):
    r = report["return"] - report["bench"] - report["cost"]
    ra = risk_analysis(r, freq="day")["risk"]  # matches PortAnaRecord (N=238)
    return ra["annualized_return"], ra["information_ratio"], ra["max_drawdown"]


def main():
    with open(CFG6) as f:
        cfg = yaml.safe_load(f)
    qlib.init(**cfg["qlib_init"])

    ds_cfg = cfg["task"]["dataset"]
    model_kwargs = dict(cfg["task"]["model"]["kwargs"])
    pa = cfg["port_analysis_config"]
    bt = pa["backtest"]

    rows = []
    for hname, hpath in HANDLERS.items():
        cls, mod = hpath.rsplit(".", 1)[1], hpath.rsplit(".", 1)[0]
        ds_cfg["kwargs"]["handler"] = {"class": cls, "module_path": mod, "kwargs": cfg["data_handler_config"]}
        dataset = init_instance_by_config(ds_cfg)  # built once per handler, reused across seeds
        for seed in SEEDS:
            model = init_instance_by_config(
                {
                    "class": "LGBModel",
                    "module_path": "qlib.contrib.model.gbdt",
                    "kwargs": {**model_kwargs, "seed": seed},
                }
            )
            model.fit(dataset)
            pred = model.predict(dataset)  # test segment, indexed (datetime, instrument)
            skwargs = {k: v for k, v in pa["strategy"]["kwargs"].items() if k != "signal"}
            strategy = {
                "class": "TopkDropoutStrategy",
                "module_path": "qlib.contrib.strategy",
                "kwargs": {"signal": pred, **skwargs},
            }
            report, _ = backtest_daily(
                start_time=bt["start_time"],
                end_time=bt["end_time"],
                strategy=strategy,
                account=bt["account"],
                benchmark=bt["benchmark"],
                exchange_kwargs=bt["exchange_kwargs"],
            )
            ann, ir, mdd = excess_with_cost(report)
            rows.append({"handler": hname, "seed": seed, "excess": ann, "IR": ir, "maxDD": mdd})
            print(f"{hname:8s} seed={seed:<5d} excess={ann:+.4f} IR={ir:+.3f} maxDD={mdd:.3f}")

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
