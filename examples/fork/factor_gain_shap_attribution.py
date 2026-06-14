#!/usr/bin/env python
# [FORK] Gain / SHAP factor attribution for the trained LightGBM (FORK.md §10 Phase 3).
#
# WHY: §9.7 showed univariate IC is the WRONG way to judge a factor inside a nonlinear
# tree model — "noise" factors (zero IC) still carried interaction signal. The correct
# attribution reads the *trained* model:
#   gain  = total loss reduction from splits on a feature (LightGBM's own importance)
#   SHAP  = mean |TreeSHAP contribution| per feature over the test set, via LightGBM's
#           built-in pred_contrib (exact tree SHAP, no external `shap` lib needed)
# Both capture nonlinear + interaction use that univariate IC misses. We report where
# our 6 custom factors rank among ALL 164 features (158 Alpha158 + 6 ours).
#
# Run:  MLFLOW_ALLOW_FILE_STORE=true .venv/bin/python examples/fork/factor_gain_shap_attribution.py

import os

import numpy as np
import pandas as pd
import yaml

import qlib
from qlib.utils import init_instance_by_config
from qlib.data.dataset.handler import DataHandlerLP
from qlib.custom.data.handler import Alpha158Custom

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(HERE, "workflow_config_lightgbm_custom_us_massive.yaml")


def main():
    with open(CONFIG) as f:
        cfg = yaml.safe_load(f)

    qlib.init(**cfg["qlib_init"])

    dataset = init_instance_by_config(cfg["task"]["dataset"])
    model = init_instance_by_config(cfg["task"]["model"])
    model.fit(dataset)
    booster = model.model

    # Feature column names, in the exact order the model was trained on.
    feat_cols = list(dataset.prepare("train", col_set=["feature"], data_key=DataHandlerLP.DK_L).columns)
    feat_cols = [c[-1] if isinstance(c, tuple) else c for c in feat_cols]  # drop the "feature" group level

    gain = booster.feature_importance(importance_type="gain")
    split = booster.feature_importance(importance_type="split")

    # TreeSHAP on the test set (last column of pred_contrib is the base/expected value).
    x_test = dataset.prepare("test", col_set="feature", data_key=DataHandlerLP.DK_I)
    contrib = booster.predict(x_test.values, pred_contrib=True)
    shap_abs = np.abs(contrib[:, :-1]).mean(axis=0)

    res = pd.DataFrame({"feature": feat_cols, "gain": gain, "split": split, "shap": shap_abs}).set_index("feature")
    res["gain_pct"] = 100 * res["gain"] / res["gain"].sum()
    res["shap_pct"] = 100 * res["shap"] / res["shap"].sum()
    res["gain_rank"] = res["gain"].rank(ascending=False).astype(int)
    res["shap_rank"] = res["shap"].rank(ascending=False).astype(int)

    n = len(res)
    custom = ["OVERNIGHT", "MOM12_1", "HI52W", "LOTTERY21", "AMIHUD21", "PVOL21"]
    pd.set_option("display.float_format", lambda x: f"{x:0.3f}")

    print(f"\nGain/SHAP attribution | {n} features (158 Alpha158 + {len(custom)} custom) | trained on 2008-2018\n")
    print("=== OUR 6 CUSTOM FACTORS (rank is out of all {} features) ===".format(n))
    print(res.loc[custom, ["gain_pct", "gain_rank", "shap_pct", "shap_rank"]].to_string())
    print(f"\n=== TOP 15 FEATURES BY SHAP (where do ours land?) ===")
    top = res.sort_values("shap", ascending=False).head(15)
    top = top[["gain_pct", "gain_rank", "shap_pct", "shap_rank"]].copy()
    top.index = [f"{i} *" if i in custom else i for i in top.index]  # star our factors
    print(top.to_string())
    cust_shap = res.loc[custom, "shap_pct"].sum()
    print(
        f"\nOur 6 custom factors together = {cust_shap:0.1f}% of total SHAP "
        f"(fair share if all equal = {100*len(custom)/n:0.1f}%)."
    )


if __name__ == "__main__":
    main()
