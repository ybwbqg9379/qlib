# [FORK] Massive (formerly Polygon) US-equity collector

Fetches US equity OHLCV from **Massive** (Polygon.io rebranded to Massive on
2025-10-30) and dumps it into qlib `.bin` format. New collector — no upstream
file is modified.

> Host: canonical REST base is now `https://api.massive.com`. The legacy
> `https://api.polygon.io` still works through the 2026 migration window (same
> API key, identical endpoints). Override with `MASSIVE_BASE_URL` in `.env`.

## 1. Configure the key (once)

Copy `.env.example` → `.env` at the repo root and fill in:

```
MASSIVE_API_KEY=<your key>          # POLYGON_API_KEY also accepted
MASSIVE_BASE_URL=https://api.massive.com
```

`.env` is gitignored. The collector auto-loads it; you can also export the vars.

## 2. Daily data

```bash
cd scripts/data_collector/massive

# 2a. download raw aggregates -> source/*.csv
python collector.py download_data \
  --source_dir ~/.qlib/stock_data/massive/source_1d \
  --interval 1d --start 2018-01-01 --end 2024-12-31 \
  --symbols ~/.qlib/qlib_data/us_data/instruments/sp500.txt \
  --delay 0.2 --max_workers 1

# 2b. normalize -> normalize/*.csv (qlib columns + factor/change)
python collector.py normalize_data \
  --source_dir ~/.qlib/stock_data/massive/source_1d \
  --normalize_dir ~/.qlib/stock_data/massive/norm_1d --interval 1d

# 2c. dump -> .bin  (include_fields = numeric cols only; never dump the text `symbol`)
python ../../dump_bin.py dump_all \
  --data_path ~/.qlib/stock_data/massive/norm_1d \
  --qlib_dir ~/.qlib/qlib_data/us_data_massive --freq day \
  --include_fields open,high,low,close,volume,vwap,factor,change
```

Then `qlib.init(provider_uri="~/.qlib/qlib_data/us_data_massive", region="us")`.

## 3. Minute data

Same three steps with `--interval 1min` and `--freq 1min`:

```bash
python collector.py download_data --interval 1min --source_dir .../source_1min \
  --start 2024-01-01 --end 2024-03-31 --symbols AAPL,MSFT --delay 0.2
python collector.py normalize_data --interval 1min --source_dir .../source_1min \
  --normalize_dir .../norm_1min
python ../../dump_bin.py dump_all --data_path .../norm_1min \
  --qlib_dir ~/.qlib/qlib_data/us_data_massive_1min --freq 1min \
  --include_fields open,high,low,close,volume,vwap,factor,change
```

> Minute history depth depends on your Massive plan; default start for `1min` is
> the last ~2 years. Pull short windows per run and respect your rate limit
> (`--delay`, `--max_workers 1`).

## Notes
- `--symbols` accepts a comma list (`AAPL,MSFT`), a path to a qlib instrument file
  (`.../sp500.txt`, tab-separated — first column used), or is omitted for a small
  smoke-test set (`AAPL, MSFT, SPY`).
- Prices are adjusted (`adjusted=true`) → `factor` is set to 1.0 on normalize.
- Index benchmark (e.g. S&P 500) on Massive is `I:SPX`, not the `^GSPC` symbol in
  the bundled Yahoo dataset — wire a benchmark separately if you need excess-return.
