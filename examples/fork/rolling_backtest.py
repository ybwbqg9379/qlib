#!/usr/bin/env python
# [FORK] Walk-forward (rolling) backtest — does the positive mean excess hold across
# market regimes, or only in the single 2021-2026 test segment? (FORK.md §10 Phase 3,
# follows §9.10.)
#
# WHY: every result so far used ONE fixed split (train 2008-2018 / test 2021-2026). A
# positive number there can be regime luck. This walks an EXPANDING window forward:
# for each test year Y, train on [2008 .. Y-2], validate on [Y-1], test on [Y]. The
# handler is rebuilt per window so normalization is fit only on that window's train
# (no lookahead). Each window is averaged over 3 seeds (§9.10: single-seed excess is
# +/-10pp noise). We then read the per-year excess distribution: how many years beat
# SPY, mean across years, worst year.
#
# Handler = Alpha158Custom5 (the default, §9.10). Run:
#   MLFLOW_ALLOW_FILE_STORE=true .venv/bin/python examples/fork/rolling_backtest.py

import os

import numpy as np
import pandas as pd
import yaml

import qlib
from qlib.utils import init_instance_by_config
from qlib.contrib.evaluate import backtest_daily, risk_analysis

HERE = os.path.dirname(os.path.abspath(__file__))
CFG = os.path.join(HERE, "workflow_config_lightgbm_custom5_us_massive.yaml")
TEST_YEARS = list(range(2016, 2027))  # 2016..2026 (2026 is partial, to 2026-06-01)
SEEDS = [0, 1, 2]
DATA_START = "2008-01-01"


def risk(report):
    r = report["return"] - report["bench"] - report["cost"]
    ra = risk_analysis(r, freq="day")["risk"]
    rb = risk_analysis(report["bench"], freq="day")["risk"]
    return ra["annualized_return"], ra["information_ratio"], ra["max_drawdown"], rb["annualized_return"]


def main():
    with open(CFG) as f:
        cfg = yaml.safe_load(f)
    qlib.init(**cfg["qlib_init"])

    handler_cfg = cfg["task"]["dataset"]["kwargs"]["handler"]  # Alpha158Custom5
    model_kwargs = dict(cfg["task"]["model"]["kwargs"])
    bt = cfg["port_analysis_config"]["backtest"]
    skwargs = {k: v for k, v in cfg["port_analysis_config"]["strategy"]["kwargs"].items() if k != "signal"}

    rows = []
    for Y in TEST_YEARS:
        train_end = f"{Y-2}-12-31"
        valid_start, valid_end = f"{Y-1}-01-01", f"{Y-1}-12-31"
        test_start = f"{Y}-01-01"
        test_end = "2026-06-01" if Y == 2026 else f"{Y}-12-31"

        dhc = dict(cfg["data_handler_config"])
        dhc.update(start_time=DATA_START, end_time=test_end, fit_start_time=DATA_START, fit_end_time=train_end)
        ds_cfg = {
            "class": "DatasetH",
            "module_path": "qlib.data.dataset",
            "kwargs": {
                "handler": {**handler_cfg, "kwargs": dhc},
                "segments": {
                    "train": [DATA_START, train_end],
                    "valid": [valid_start, valid_end],
                    "test": [test_start, test_end],
                },
            },
        }
        dataset = init_instance_by_config(ds_cfg)  # rebuilt per window: norm fit on train only

        ex_seeds = []
        for seed in SEEDS:
            model = init_instance_by_config(
                {
                    "class": "LGBModel",
                    "module_path": "qlib.contrib.model.gbdt",
                    "kwargs": {**model_kwargs, "seed": seed},
                }
            )
            model.fit(dataset)
            pred = model.predict(dataset)
            strategy = {
                "class": "TopkDropoutStrategy",
                "module_path": "qlib.contrib.strategy",
                "kwargs": {"signal": pred, **skwargs},
            }
            report, _ = backtest_daily(
                start_time=test_start,
                end_time=test_end,
                strategy=strategy,
                account=bt["account"],
                benchmark=bt["benchmark"],
                exchange_kwargs=bt["exchange_kwargs"],
            )
            ex, ir, mdd, bench = risk(report)
            ex_seeds.append((ex, ir, mdd, bench))
        arr = np.array(ex_seeds)
        ex_m, ir_m, mdd_m, bench_m = arr.mean(axis=0)
        rows.append({"test_year": Y, "excess": ex_m, "IR": ir_m, "maxDD": mdd_m, "bench": bench_m})
        print(f"test {Y}: excess={ex_m:+.4f} (IR {ir_m:+.3f}, maxDD {mdd_m:.3f}) | SPY {bench_m:+.4f}")

    df = pd.DataFrame(rows).set_index("test_year")
    pd.set_option("display.float_format", lambda x: f"{x:0.4f}")
    print("\n=== walk-forward excess-with-cost by test year (mean of 3 seeds) ===")
    print(df.to_string())
    ex = df["excess"]
    print(
        f"\nVERDICT: positive-excess years {(ex > 0).sum()}/{len(ex)} | "
        f"mean across years {ex.mean():+.4f} +/- {ex.std():.4f} | worst {ex.min():+.4f} ({ex.idxmin()}) | "
        f"{'robust across regimes' if (ex > 0).mean() >= 0.7 and ex.mean() > 0 else 'NOT robust — concentrated in some regimes'}"
    )


if __name__ == "__main__":
    main()
