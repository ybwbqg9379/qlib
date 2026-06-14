# [FORK] Alpha Vantage US-equity data collector — see FORK.md §5.3.
#
# New collector, no upstream file touched. Same shape as the bundled `yahoo`
# collector (BaseCollector / BaseNormalize / BaseRun + fire CLI):
#
#   1) cd scripts/data_collector/alpha_vantage
#   2) python collector.py download_data  --source_dir ~/.qlib/stock_data/av/source \
#          --interval 1d --symbols AAPL,MSFT --delay 1
#   3) python collector.py normalize_data --source_dir ~/.qlib/stock_data/av/source \
#          --normalize_dir ~/.qlib/stock_data/av/normalize --interval 1d
#   4) python ../../dump_bin.py dump_all  --data_path ~/.qlib/stock_data/av/normalize \
#          --qlib_dir ~/.qlib/qlib_data/us_data_av --freq day \
#          --include_fields open,high,low,close,volume,factor,change
#
# Key comes from .env (repo root): ALPHA_VANTAGE_API_KEY.
#
# Rate limits: Alpha Vantage free tier is ~25 requests/day & 5/min — use --delay
# and small --symbols sets, or a premium key for bulk. 1min intraday history is
# paged by calendar month (`month=YYYY-MM`).
import os
import sys
import time
import datetime
from pathlib import Path
from typing import Iterable, Optional

import fire
import requests
import pandas as pd
from loguru import logger

CUR_DIR = Path(__file__).resolve().parent
sys.path.append(str(CUR_DIR.parent.parent))
from data_collector.base import BaseCollector, BaseNormalize, BaseRun  # noqa: E402

_AV_URL = "https://www.alphavantage.co/query"


def _load_env():
    try:
        from dotenv import load_dotenv

        load_dotenv(CUR_DIR.parents[2].joinpath(".env"))
    except Exception:
        pass


def _api_key() -> str:
    _load_env()
    key = os.environ.get("ALPHA_VANTAGE_API_KEY")
    if not key:
        raise RuntimeError(
            "No ALPHA_VANTAGE_API_KEY. Put it in the repo-root .env (copy .env.example) "
            "or export it. See FORK.md §5.3."
        )
    return key


def _read_symbols(symbols) -> list:
    if symbols is None:
        logger.warning("No --symbols given; defaulting to a small smoke-test set [AAPL, MSFT].")
        return ["AAPL", "MSFT"]
    if isinstance(symbols, (list, tuple)):
        return [str(s).strip() for s in symbols if str(s).strip()]
    s = str(symbols)
    p = Path(s).expanduser()
    if p.exists():
        out = []
        for line in p.read_text().splitlines():
            tok = line.strip().split("\t")[0].split(",")[0].strip()
            if tok:
                out.append(tok)
        return sorted(set(out))
    return [tok.strip() for tok in s.split(",") if tok.strip()]


def _months(start: pd.Timestamp, end: pd.Timestamp) -> list:
    """Inclusive list of YYYY-MM strings between start and end (for intraday paging)."""
    cur = pd.Timestamp(start).replace(day=1)
    last = pd.Timestamp(end).replace(day=1)
    out = []
    while cur <= last:
        out.append(cur.strftime("%Y-%m"))
        cur = (cur + pd.Timedelta(days=32)).replace(day=1)
    return out


class AlphaVantageCollector(BaseCollector):
    # AV intraday extended history goes back ~2 years on most tiers.
    DEFAULT_START_DATETIME_1MIN = pd.Timestamp(datetime.datetime.now() - pd.Timedelta(days=730)).date()

    def __init__(self, save_dir, symbols=None, **kwargs):
        self._symbols_arg = symbols
        self._session = requests.Session()
        self._key = _api_key()
        super().__init__(save_dir=save_dir, **kwargs)

    def get_instrument_list(self) -> list:
        return _read_symbols(self._symbols_arg)

    def normalize_symbol(self, symbol: str) -> str:
        return str(symbol).strip().upper()

    def _get(self, params: dict) -> dict:
        params = {**params, "apikey": self._key}
        for _ in range(5):
            resp = self._session.get(_AV_URL, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            # AV signals throttling via a "Note"/"Information" message, HTTP 200.
            if "Note" in data or "Information" in data:
                logger.warning(f"AV throttle: {data.get('Note') or data.get('Information')}; sleeping 60s")
                time.sleep(60)
                continue
            if "Error Message" in data:
                logger.warning(f"AV error for {params.get('symbol')}: {data['Error Message']}")
                return {}
            return data
        return {}

    def get_data(
        self, symbol: str, interval: str, start_datetime: pd.Timestamp, end_datetime: pd.Timestamp
    ) -> pd.DataFrame:
        if interval == self.INTERVAL_1d:
            frames = [self._get_daily(symbol)]
        else:
            frames = [self._get_intraday(symbol, m) for m in _months(start_datetime, end_datetime)]
        frames = [f for f in frames if f is not None and not f.empty]
        if not frames:
            return pd.DataFrame()
        df = pd.concat(frames, ignore_index=True)
        mask = (pd.to_datetime(df["date"]) >= pd.Timestamp(start_datetime)) & (
            pd.to_datetime(df["date"]) <= pd.Timestamp(end_datetime) + pd.Timedelta(days=1)
        )
        return df[mask].reset_index(drop=True)

    def _get_daily(self, symbol: str) -> pd.DataFrame:
        data = self._get({"function": "TIME_SERIES_DAILY_ADJUSTED", "symbol": symbol, "outputsize": "full"})
        series = data.get("Time Series (Daily)", {})
        rows = []
        for day, v in series.items():
            rows.append(
                {
                    "symbol": self.normalize_symbol(symbol),
                    "date": day,
                    "open": v.get("1. open"),
                    "high": v.get("2. high"),
                    "low": v.get("3. low"),
                    "close": v.get("4. close"),  # raw close
                    "adjclose": v.get("5. adjusted close"),
                    "volume": v.get("6. volume"),
                }
            )
        return pd.DataFrame(rows)

    def _get_intraday(self, symbol: str, month: str) -> pd.DataFrame:
        data = self._get(
            {
                "function": "TIME_SERIES_INTRADAY",
                "symbol": symbol,
                "interval": "1min",
                "outputsize": "full",
                "month": month,
                "extended_hours": "false",
            }
        )
        series = data.get("Time Series (1min)", {})
        rows = []
        for ts, v in series.items():
            rows.append(
                {
                    "symbol": self.normalize_symbol(symbol),
                    "date": ts,
                    "open": v.get("1. open"),
                    "high": v.get("2. high"),
                    "low": v.get("3. low"),
                    "close": v.get("4. close"),
                    "volume": v.get("5. volume"),
                }
            )
        return pd.DataFrame(rows)


class AlphaVantageNormalize(BaseNormalize):
    COLUMNS = ["open", "high", "low", "close", "volume"]

    def _get_calendar_list(self) -> Optional[Iterable[pd.Timestamp]]:
        return None  # dump_bin derives the calendar from the data

    def normalize(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df
        df = df.copy()
        df[self._date_field_name] = pd.to_datetime(df[self._date_field_name])
        df = df.drop_duplicates(subset=[self._date_field_name]).sort_values(self._date_field_name)
        df = df.set_index(self._date_field_name)
        for col in self.COLUMNS + ["adjclose"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        # qlib `factor` = adjusted/raw close; backfills splits/dividends. Daily has
        # adjclose; intraday doesn't (factor=1).
        if "adjclose" in df.columns and "close" in df.columns:
            df["factor"] = (df["adjclose"] / df["close"]).fillna(1.0)
            df = df.drop(columns=["adjclose"])
        else:
            df["factor"] = 1.0
        if "close" in df.columns:
            df["change"] = df["close"].pct_change()
        df.index.names = [self._date_field_name]
        return df.reset_index()


class Run(BaseRun):
    @property
    def collector_class_name(self):
        return "AlphaVantageCollector"

    @property
    def normalize_class_name(self):
        return "AlphaVantageNormalize"

    @property
    def default_base_dir(self):
        return CUR_DIR.joinpath("av_data")


if __name__ == "__main__":
    fire.Fire(Run)
