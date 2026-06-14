# [FORK] Shared evaluation helpers for the examples/fork research scripts.
#
# WHY: multiseed_compare.py and rolling_backtest.py (and partly the attribution
# scripts) each repeated the same "load cfg -> build DatasetH -> train LGBModel with a
# seed -> TopkDropout backtest -> excess-with-cost risk metrics" block. A change to the
# evaluation logic had to be made in several places. This centralizes it so every fork
# study computes performance the SAME way (and matches PortAnaRecord: excess = return -
# bench - cost, risk_analysis with freq="day" -> N=238).
import copy

import yaml

from qlib.utils import init_instance_by_config
from qlib.contrib.evaluate import backtest_daily, risk_analysis


def load_cfg(path):
    with open(path) as f:
        return yaml.safe_load(f)


def build_dataset(cfg, handler_class=None, data_handler_config=None, segments=None):
    """Build a DatasetH from a workflow cfg, with optional overrides.

    handler_class : "a.b.c.ClassName" to swap the handler (else use cfg's).
    data_handler_config : dict of handler kwargs (else cfg["data_handler_config"]).
    segments : {"train":[...], "valid":[...], "test":[...]} (else cfg's).
    Each call builds a fresh dataset so per-window normalization has no lookahead.
    """
    ds_cfg = copy.deepcopy(cfg["task"]["dataset"])
    handler = ds_cfg["kwargs"]["handler"]
    if handler_class is not None:
        mod, cls = handler_class.rsplit(".", 1)
        handler["module_path"], handler["class"] = mod, cls
    handler["kwargs"] = data_handler_config if data_handler_config is not None else cfg["data_handler_config"]
    if segments is not None:
        ds_cfg["kwargs"]["segments"] = segments
    return init_instance_by_config(ds_cfg)


def train_predict(cfg, dataset, seed=None):
    """Train an LGBModel (cfg's kwargs, optional seed override) and return (model, pred)."""
    mk = dict(cfg["task"]["model"]["kwargs"])
    if seed is not None:
        mk["seed"] = seed
    model = init_instance_by_config({"class": "LGBModel", "module_path": "qlib.contrib.model.gbdt", "kwargs": mk})
    model.fit(dataset)
    return model, model.predict(dataset)


def backtest_excess(cfg, pred, start, end):
    """Run the cfg's TopkDropout backtest on `pred` and return excess-with-cost metrics.

    Returns {"excess", "IR", "maxDD", "bench"} — annualized excess-return-with-cost,
    its information ratio and max drawdown, and the benchmark's annualized return.
    Matches PortAnaRecord: excess = return - bench - cost; risk_analysis(freq="day").
    """
    pa = cfg["port_analysis_config"]
    bt = pa["backtest"]
    skwargs = {k: v for k, v in pa["strategy"]["kwargs"].items() if k != "signal"}
    strategy = {
        "class": "TopkDropoutStrategy",
        "module_path": "qlib.contrib.strategy",
        "kwargs": {"signal": pred, **skwargs},
    }
    report, _ = backtest_daily(
        start_time=start,
        end_time=end,
        strategy=strategy,
        account=bt["account"],
        benchmark=bt["benchmark"],
        exchange_kwargs=bt["exchange_kwargs"],
    )
    r = report["return"] - report["bench"] - report["cost"]
    ra = risk_analysis(r, freq="day")["risk"]
    rb = risk_analysis(report["bench"], freq="day")["risk"]
    return {
        "excess": ra["annualized_return"],
        "IR": ra["information_ratio"],
        "maxDD": ra["max_drawdown"],
        "bench": rb["annualized_return"],
    }
