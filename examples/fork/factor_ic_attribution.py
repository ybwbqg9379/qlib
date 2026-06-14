#!/usr/bin/env python
# [FORK] Single-factor IC attribution for our custom factors (FORK.md §10 Phase 3).
#
# WHY: the LightGBM backtest only tells us the 6 custom factors *together* beat the
# baseline. It does NOT tell us WHICH factors carry the signal and which drag. This
# computes per-factor cross-sectional IC so we can keep the winners and drop/flip the
# losers before the next iteration.
#
# WHAT it reports per factor, over the same test window as the backtest:
#   IC      = mean over days of Pearson corr(factor_t, fwd_return_t) across stocks
#   RankIC  = same with Spearman (rank) corr — robust to outliers/scale
#   ICIR    = mean(daily RankIC) / std(daily RankIC)  (consistency, unitless)
#   t-stat  = ICIR * sqrt(n_days)                     (is RankIC reliably != 0?)
#   |RankIC|>0.02 and |t|>2 are the rough "worth keeping" bars.
#
# Run:  MLFLOW_ALLOW_FILE_STORE=true .venv/bin/python examples/fork/factor_ic_attribution.py

import numpy as np
import pandas as pd

import qlib
from qlib.data import D
from qlib.custom.data.handler import Alpha158Custom

PROVIDER_URI = "~/.qlib/qlib_data/us_data_massive"
MARKET = "all"
# Match the backtest's test segment (workflow_config_lightgbm_custom_us_massive.yaml).
TEST_START, TEST_END = "2021-01-01", "2026-06-01"
# Same forward-return label Alpha158 trains on: next day's open-to-open style return.
LABEL_EXPR = "Ref($close, -2)/Ref($close, -1) - 1"


def daily_ic(df, factor_col, label_col, method):
    """Mean and per-day series of cross-sectional corr between a factor and the label."""

    def _one_day(g):
        sub = g[[factor_col, label_col]].dropna()
        if len(sub) < 10:  # need enough names for a meaningful cross-section
            return np.nan
        return sub[factor_col].corr(sub[label_col], method=method)

    per_day = df.groupby(level="datetime", group_keys=False).apply(_one_day)
    return per_day.dropna()


def main():
    qlib.init(provider_uri=PROVIDER_URI, region="us")

    fields, names = Alpha158Custom.get_custom_feature_config()
    cols = names + ["LABEL"]
    exprs = fields + [LABEL_EXPR]

    insts = D.instruments(market=MARKET)
    df = D.features(insts, exprs, start_time=TEST_START, end_time=TEST_END, freq="day")
    df.columns = cols

    rows = []
    for f in names:
        ic = daily_ic(df, f, "LABEL", "pearson")
        ric = daily_ic(df, f, "LABEL", "spearman")
        icir = ric.mean() / ric.std() if ric.std() > 0 else np.nan
        tstat = icir * np.sqrt(len(ric)) if not np.isnan(icir) else np.nan
        rows.append(
            {
                "factor": f,
                "IC": ic.mean(),
                "RankIC": ric.mean(),
                "ICIR": icir,
                "t_stat": tstat,
                "n_days": len(ric),
            }
        )

    res = pd.DataFrame(rows).set_index("factor")
    res = res.reindex(res["RankIC"].abs().sort_values(ascending=False).index)  # strongest first
    pd.set_option("display.float_format", lambda x: f"{x:0.4f}")
    print(f"\nSingle-factor IC attribution | market={MARKET} | test {TEST_START}..{TEST_END}\n")
    print(res.to_string())
    print(
        "\nReading: RankIC sign = direction of prediction (negative = the factor predicts"
        "\nLOW returns, still useful — LightGBM can flip it). |RankIC|>0.02 & |t|>2 ~ keep."
    )


if __name__ == "__main__":
    main()
