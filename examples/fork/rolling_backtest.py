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
import sys

import numpy as np
import pandas as pd

import qlib
from _eval import load_cfg, build_dataset, train_predict, backtest_excess

HERE = os.path.dirname(os.path.abspath(__file__))
# optional CLI arg = workflow config path (default = the Custom5 default handler)
CFG = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "workflow_config_lightgbm_custom5_us_massive.yaml")
TEST_YEARS = list(range(2016, 2027))  # 2016..2026 (2026 is partial, to 2026-06-01)
SEEDS = [0, 1, 2]
DATA_START = "2008-01-01"


def main():
    cfg = load_cfg(CFG)
    qlib.init(**cfg["qlib_init"])

    rows = []
    for Y in TEST_YEARS:
        train_end = f"{Y-2}-12-31"
        test_start = f"{Y}-01-01"
        test_end = "2026-06-01" if Y == 2026 else f"{Y}-12-31"

        dhc = dict(cfg["data_handler_config"])
        dhc.update(start_time=DATA_START, end_time=test_end, fit_start_time=DATA_START, fit_end_time=train_end)
        segments = {
            "train": [DATA_START, train_end],
            "valid": [f"{Y-1}-01-01", f"{Y-1}-12-31"],
            "test": [test_start, test_end],
        }
        # rebuilt per window so normalization is fit on this window's train only (no lookahead)
        dataset = build_dataset(cfg, data_handler_config=dhc, segments=segments)

        per_seed = []
        for seed in SEEDS:
            _, pred = train_predict(cfg, dataset, seed=seed)
            m = backtest_excess(cfg, pred, test_start, test_end)
            per_seed.append([m["excess"], m["IR"], m["maxDD"], m["bench"]])
        ex_m, ir_m, mdd_m, bench_m = np.array(per_seed).mean(axis=0)
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
