# [FORK] Massive (formerly Polygon) US-equity data collector — see FORK.md §5.3.
#
# New collector, no upstream file touched. Same shape as the bundled `yahoo`
# collector (BaseCollector / BaseNormalize / BaseRun + fire CLI), so it plugs
# into the standard pipeline:
#
#   1) cd scripts/data_collector/massive
#   2) python collector.py download_data  --source_dir ~/.qlib/stock_data/massive/source \
#          --interval 1d   --start 2018-01-01 --end 2024-12-31 --symbols AAPL,MSFT,SPY
#   3) python collector.py normalize_data --source_dir ~/.qlib/stock_data/massive/source \
#          --normalize_dir ~/.qlib/stock_data/massive/normalize --interval 1d
#   4) python ../../dump_bin.py dump_all  --data_path ~/.qlib/stock_data/massive/normalize \
#          --qlib_dir ~/.qlib/qlib_data/us_data_massive --freq day \
#          --include_fields open,high,low,close,volume,vwap,factor,change
#
# For minute data use --interval 1min everywhere and --freq 1min in dump_bin.
#
# Auth/host come from .env (repo root): MASSIVE_API_KEY (or legacy POLYGON_API_KEY)
# and MASSIVE_BASE_URL. Polygon.io became Massive on 2025-10-30; default host is
# now https://api.massive.com (old https://api.polygon.io still works through the
# 2026 migration window — same key, identical endpoints).
import os
import sys
import time
import datetime
from pathlib import Path
from typing import Iterable, Optional

import fire
import requests
import numpy as np
import pandas as pd
from loguru import logger

CUR_DIR = Path(__file__).resolve().parent
sys.path.append(str(CUR_DIR.parent.parent))  # repo scripts/ on path → dump_bin, data_collector
from data_collector.base import BaseCollector, BaseNormalize, BaseRun  # noqa: E402


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _load_env():
    """Load repo-root .env so MASSIVE_API_KEY / MASSIVE_BASE_URL are available."""
    try:
        from dotenv import load_dotenv

        load_dotenv(CUR_DIR.parents[2].joinpath(".env"))
    except Exception:  # dotenv optional; real env vars still work
        pass


def _api_key() -> str:
    _load_env()
    key = os.environ.get("MASSIVE_API_KEY") or os.environ.get("POLYGON_API_KEY")
    if not key:
        raise RuntimeError(
            "No Massive/Polygon API key. Put MASSIVE_API_KEY=<key> in the repo-root .env "
            "(copy .env.example), or export it. See FORK.md §5.3."
        )
    return key


def _base_url() -> str:
    # Polygon.io rebranded to Massive (2025-10-30); canonical REST host is now
    # api.massive.com. The old api.polygon.io still works in parallel during the
    # 2026 migration window (same keys, identical endpoints) — override via
    # MASSIVE_BASE_URL if needed.
    _load_env()
    return (os.environ.get("MASSIVE_BASE_URL") or "https://api.massive.com").rstrip("/")


def _read_symbols(symbols) -> list:
    """Accept a comma string, a path to a .txt (one symbol per line / qlib instrument
    file), a list, or None (→ small default smoke-test set)."""
    if symbols is None:
        logger.warning("No --symbols given; defaulting to a small smoke-test set [AAPL, MSFT, SPY].")
        return ["AAPL", "MSFT", "SPY"]
    if isinstance(symbols, (list, tuple)):
        return [str(s).strip() for s in symbols if str(s).strip()]
    s = str(symbols)
    p = Path(s).expanduser()
    if p.exists():
        out = []
        for line in p.read_text().splitlines():
            tok = line.strip().split("\t")[0].split(",")[0].strip()  # qlib instrument files are tab-sep
            if tok:
                out.append(tok)
        return sorted(set(out))
    return [tok.strip() for tok in s.split(",") if tok.strip()]


# --------------------------------------------------------------------------- #
# collector
# --------------------------------------------------------------------------- #
class MassiveCollector(BaseCollector):
    # Massive minute history depth depends on plan; default to last ~2 years on free/basic.
    DEFAULT_START_DATETIME_1MIN = pd.Timestamp(datetime.datetime.now() - pd.Timedelta(days=730)).date()

    def __init__(self, save_dir, symbols=None, adjusted=True, **kwargs):
        self._symbols_arg = symbols
        self._adjusted = bool(adjusted)
        self._session = requests.Session()
        self._session.headers.update({"Authorization": f"Bearer {_api_key()}"})
        self._base = _base_url()
        super().__init__(save_dir=save_dir, **kwargs)

    def get_instrument_list(self) -> list:
        return _read_symbols(self._symbols_arg)

    def normalize_symbol(self, symbol: str) -> str:
        return str(symbol).strip().upper()

    def get_data(
        self, symbol: str, interval: str, start_datetime: pd.Timestamp, end_datetime: pd.Timestamp
    ) -> pd.DataFrame:
        timespan = "minute" if interval == self.INTERVAL_1min else "day"
        frm = pd.Timestamp(start_datetime).strftime("%Y-%m-%d")
        to = pd.Timestamp(end_datetime).strftime("%Y-%m-%d")
        url = (
            f"{self._base}/v2/aggs/ticker/{symbol.upper()}/range/1/{timespan}/{frm}/{to}"
            f"?adjusted={'true' if self._adjusted else 'false'}&sort=asc&limit=50000"
        )
        rows = []
        while url:
            resp = self._session.get(url, timeout=30)
            if resp.status_code == 429:  # rate limited → back off and retry same url
                logger.warning(f"{symbol}: 429 rate-limited, sleeping 15s")
                time.sleep(15)
                continue
            resp.raise_for_status()
            payload = resp.json()
            rows.extend(payload.get("results", []) or [])
            nxt = payload.get("next_url")
            url = f"{nxt}&apiKey={_api_key()}" if nxt else None  # next_url needs the key re-appended
        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows)
        # Polygon aggregate fields: t(ms), o,h,l,c,v, vw(vwap), n(trades)
        ts = pd.to_datetime(df["t"], unit="ms", utc=True).dt.tz_convert("America/New_York")
        df["date"] = ts.dt.strftime("%Y-%m-%d") if timespan == "day" else ts.dt.strftime("%Y-%m-%d %H:%M:%S")
        df = df.rename(columns={"o": "open", "h": "high", "l": "low", "c": "close", "v": "volume", "vw": "vwap"})
        df["symbol"] = self.normalize_symbol(symbol)
        keep = ["symbol", "date", "open", "high", "low", "close", "volume", "vwap"]
        return df[[c for c in keep if c in df.columns]]


class MassiveNormalize(BaseNormalize):
    COLUMNS = ["open", "high", "low", "close", "volume"]

    def _get_calendar_list(self) -> Optional[Iterable[pd.Timestamp]]:
        # No fixed benchmark calendar: dump_bin builds the calendar from the union
        # of all symbols' dates. Per-symbol normalize just cleans + orders rows.
        return None

    def normalize(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df
        df = df.copy()
        df[self._date_field_name] = pd.to_datetime(df[self._date_field_name])
        df = df.drop_duplicates(subset=[self._date_field_name]).sort_values(self._date_field_name)
        df = df.set_index(self._date_field_name)
        for col in self.COLUMNS:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        # qlib convention: `factor` = adjustment factor; Massive prices are already
        # adjusted (adjusted=true), so factor is 1.0. `change` = daily pct change.
        if "close" in df.columns:
            df["change"] = df["close"].pct_change()
        df["factor"] = 1.0
        df.index.names = [self._date_field_name]
        return df.reset_index()


class Run(BaseRun):
    @property
    def collector_class_name(self):
        return "MassiveCollector"

    @property
    def normalize_class_name(self):
        return "MassiveNormalize"

    @property
    def default_base_dir(self):
        return CUR_DIR.joinpath("massive_data")


if __name__ == "__main__":
    fire.Fire(Run)
