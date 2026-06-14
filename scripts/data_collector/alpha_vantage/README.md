# [FORK] Alpha Vantage US-equity collector

Fetches US equity OHLCV from **Alpha Vantage** and dumps it into qlib `.bin`
format. New collector — no upstream file is modified.

## 1. Configure the key (once)

Copy `.env.example` → `.env` at the repo root and fill in:

```
ALPHA_VANTAGE_API_KEY=<your key>
```

`.env` is gitignored. The collector auto-loads it; you can also export the var.

## 2. Daily data (split/dividend-adjusted)

```bash
cd scripts/data_collector/alpha_vantage

python collector.py download_data \
  --source_dir ~/.qlib/stock_data/av/source_1d \
  --interval 1d --symbols AAPL,MSFT --delay 1 --max_workers 1
python collector.py normalize_data \
  --source_dir ~/.qlib/stock_data/av/source_1d \
  --normalize_dir ~/.qlib/stock_data/av/norm_1d --interval 1d
python ../../dump_bin.py dump_all \
  --data_path ~/.qlib/stock_data/av/norm_1d \
  --qlib_dir ~/.qlib/qlib_data/us_data_av --freq day \
  --include_fields open,high,low,close,volume,factor,change
```

Then `qlib.init(provider_uri="~/.qlib/qlib_data/us_data_av", region="us")`.

## 3. Minute (1min) data

Same three steps with `--interval 1min` / `--freq 1min`. Intraday is paged by
calendar month under the hood (`month=YYYY-MM`), so a wide date range = many
requests:

```bash
python collector.py download_data --interval 1min \
  --source_dir ~/.qlib/stock_data/av/source_1min \
  --symbols AAPL --start 2024-01-01 --end 2024-03-31 --delay 1
python collector.py normalize_data --interval 1min \
  --source_dir ~/.qlib/stock_data/av/source_1min \
  --normalize_dir ~/.qlib/stock_data/av/norm_1min
python ../../dump_bin.py dump_all --data_path ~/.qlib/stock_data/av/norm_1min \
  --qlib_dir ~/.qlib/qlib_data/us_data_av_1min --freq 1min \
  --include_fields open,high,low,close,volume,factor,change
```

## ⚠️ Rate limits
- **Free tier ≈ 25 requests/day and 5/min.** Each daily symbol = 1 request; each
  intraday symbol-month = 1 request. Bulk pulls need a premium key.
- The collector auto-detects AV's throttle `Note`/`Information` responses and
  sleeps 60s. Still, keep `--max_workers 1` and a `--delay`, and pull small
  symbol sets at a time.

## Notes
- `--symbols` accepts a comma list, a qlib instrument file path (tab-separated,
  first column used), or is omitted for a smoke-test set (`AAPL, MSFT`).
- Daily uses `TIME_SERIES_DAILY_ADJUSTED`: `factor = adjusted_close / close`
  (qlib's adjustment factor). Intraday has no adjusted field → `factor = 1`.
- Alpha Vantage also serves fundamentals/news (not collected here) — a natural
  next addition for fundamental factors.
