# [FORK] This package holds all of this fork's own logic (see FORK.md §2).
#
# Why a NEW sub-package instead of editing upstream qlib code:
#   qlib's whole config system (`init_instance_by_config` + a `module_path` in
#   any workflow YAML) can instantiate ANY importable class — model, dataset,
#   data handler (factors), strategy, processor, record. So custom models /
#   factors / strategies / data sources live here and are wired in purely by
#   referencing `qlib.custom.<...>` from YAML, with ZERO changes to upstream
#   files. That keeps `git merge upstream/main` conflict-free.
#
# Upstream will never create a `qlib/custom/` directory, so this sub-package
# cannot collide with future upstream code.
#
# Layout (created on demand — keep each concern in its own module):
#   qlib/custom/data/       custom DataHandlers / factor sets (subclass Alpha158, etc.)
#   qlib/custom/model/      custom models (subclass qlib.model.base.Model)
#   qlib/custom/strategy/   custom strategies (subclass BaseSignalStrategy)
#   qlib/custom/...         anything else that is ours
#
# Collectors for external data vendors (Alpha Vantage / Polygon) live under
# scripts/data_collector/<vendor>/ (same shape as the existing yahoo collector),
# because they are pre-`dump_bin` CSV producers, not import-time library code.
