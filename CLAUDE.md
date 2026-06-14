# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## This is a fork

This repo is a **self-use fork** of `microsoft/qlib` (`upstream` remote;
`origin` = `ybwbqg9379/qlib`). **Read `FORK.md` before making changes** — it
defines the customization policy: prefer extension over modification, put all our
own logic in `qlib/custom/` (a new sub-package wired in purely via YAML
`module_path`, no upstream edits), mark unavoidable upstream edits with `# [FORK]`,
log every divergence in `FORK.md §6`, and sync upstream via `git merge upstream/main`
(never rebase). No PRs are sent upstream. **Focus = US equities** (we hold Alpha
Vantage + Massive/Polygon data subscriptions).

**Before committing:** a local `commit-msg` gate enforces Conventional Commits +
a mandatory `Fork: <reason>` trailer on every commit we author (`FORK.md §3`). If
`git config --get core.hooksPath` is empty, run `./scripts/setup-hooks.sh` once first.
Subject: `type(scope): description` (same format as upstream's commitlint); add a
`Fork:` trailer line in the body.

## Commands

```bash
# Setup (package name: pyqlib; import qlib; Python 3.8–3.12)
pip install -e .              # or: make dev   (installs dev/lint/docs/test extras)
make prerequisites            # compile Cython ops (first run)
./scripts/setup-hooks.sh      # enable the commit gate (once per clone)

# Data + a benchmark run (sanity check the env)
python scripts/get_data.py qlib_data --target_dir ~/.qlib/qlib_data/us_data --region us
qrun examples/benchmarks/LightGBM/workflow_config_lightgbm_Alpha158.yaml

# Tests (pytest; "slow" excluded by default — see tests/pytest.ini)
cd tests && pytest . -m "not slow"
pytest tests/test_dump_data.py            # single file
pytest tests/storage_tests/               # a subdir

# Lint/format (upstream CI runs these; black uses 120-col)
make lint                                 # black + pylint + flake8 + mypy + nbqa
make black                                # black qlib -l 120
```

## Architecture

Qlib is an **AI-oriented quantitative investment platform**: it goes from market
data → factors/features → ML models → portfolio strategy → backtest, all driven
by declarative YAML configs.

### The one extension mechanism to know: `init_instance_by_config`
`qlib/utils/mod.py::init_instance_by_config()` instantiates **any importable
class** from a `{class, module_path, kwargs}` dict. Every workflow YAML uses it,
so you can point `module_path` at our own classes (`qlib.custom.*`) for models,
datasets, data handlers (factors), strategies, processors, and records **without
touching upstream code**. This is THE fork-friendly seam — see `FORK.md §2`.

### Workflow / config (`qrun`)
`qlib/cli/run.py::workflow()` is the `qrun <config.yaml>` entry point. A
`workflow_config_*.yaml` has: `qlib_init` (provider_uri + region) → `task.model`
→ `task.dataset` (a `DatasetH` wrapping a `DataHandler` with train/valid/test
`segments`) → `task.record` (SignalRecord / SigAnaRecord / PortAnaRecord for
backtest). `qlib/model/trainer.py::task_train()` runs it: init model + dataset,
`model.fit(dataset)`, fill `<MODEL>`/`<DATASET>`/`<PRED>` placeholders, run records.
Reference template: `examples/benchmarks/Linear/workflow_config_linear_Alpha158.yaml`.

### Data layer (`qlib/data/`)
File-backed `.bin` format. Provider base classes (`Calendar/Instrument/Feature/
PIT/Expression/Dataset Provider`) live in `qlib/data/data.py`; storage backends in
`qlib/data/storage/` (`file_storage.py`). `qlib.init(provider_uri, region)`
(`qlib/__init__.py`, `qlib/config.py`) wires providers; `region="us"` (`REG_US`)
supports US equities. **Ingesting external data** = collector → CSV → `scripts/dump_bin.py`
→ `.bin`. Existing collectors live in `scripts/data_collector/` (`yahoo/` is the
reference); there is **no** Alpha Vantage / Polygon collector yet — that's ours to add
under `scripts/data_collector/<vendor>/` (see `FORK.md §5.3`).

### Models, factors, strategies (`qlib/contrib/`)
- **Models**: `qlib/model/base.py::Model` (implement `fit`/`predict`). Built-ins in
  `qlib/contrib/model/` (gbdt/xgboost/catboost/linear + many pytorch_* nets).
- **Factors/handlers**: `qlib/contrib/data/handler.py` (`Alpha158`, `Alpha360`);
  feature exprs in `qlib/contrib/data/loader.py`. Subclass to define custom factors.
- **Strategies**: `qlib/contrib/strategy/` (`BaseSignalStrategy`, `TopkDropoutStrategy`).
- **Our custom versions** go in `qlib/custom/{model,data,strategy}/` and are referenced
  by `module_path` in YAML — never by editing the `contrib` files.

### qlib itself has no LLM code
LLM-driven factor/model mining is the sister project **RD-Agent** (external).
For local inference, point an OpenAI-compatible client at llama.cpp
(`http://localhost:8080/v1`); see `~/CLAUDE.md` for the workstation/model setup.

## Conventions

- **Extension over modification.** Custom logic lives in `qlib/custom/` (new
  sub-package) and external collectors in `scripts/data_collector/<vendor>/`,
  wired in via YAML `module_path` — keep upstream files untouched so
  `git merge upstream/main` stays conflict-free.
- **Mark + log any unavoidable upstream edit.** `# [FORK] reason` at the edit
  site (greppable) and a row in `FORK.md §6`.
- **Commit gate.** Conventional Commits subject + `Fork:` trailer, enforced by
  `.githooks/commit-msg`. Merge commits (how upstream arrives) are auto-allowed.
- **US-first.** `region="us"`; prefer our Alpha Vantage / Polygon data over the
  default yfinance/cn paths.
- Tests are the spec — `tests/` filenames map to features (dump/storage/dataset/
  backtest/ops). Style follows upstream: black 120-col, flake8 ignores E501.
```
