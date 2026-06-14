# [FORK] Alpha Vantage FUNDAMENTALS collector — point-in-time value/quality data.
# (FORK.md §10 Phase 3; the §9.11 diagnosis = need non-momentum diversifiers.)
#
# Separate from collector.py (prices). Produces qlib PIT-format CSVs (one per symbol,
# columns: date, period, field, value) for `scripts/dump_pit.py`, NOT dump_bin.
#
#   1) cd scripts/data_collector/alpha_vantage
#   2) python fundamentals.py download_data  --source_dir ~/.qlib/stock_data/av/fund \
#          --symbols ~/.qlib/qlib_data/us_data/instruments/sp500.txt --start 2008-01-01 --end 2026-06-01
#   3) python fundamentals.py normalize_data --source_dir ~/.qlib/stock_data/av/fund \
#          --normalize_dir ~/.qlib/stock_data/av/fund_norm
#   4) cd ../.. && python dump_pit.py dump --data_path ~/.qlib/stock_data/av/fund_norm \
#          --qlib_dir ~/.qlib/qlib_data/us_data_massive --interval quarterly
#      (dumps PIT .bin alongside the price .bin so handlers can read $$<field> factors)
#
# POINT-IN-TIME (the whole point): each row's `date` = when the market LEARNED the number
# = the EARNINGS `reportedDate` for that fiscal quarter. INCOME/BALANCE items carry only
# `fiscalDateEnding`, so we join them to the matching quarter's reportedDate; if missing,
# we fall back to fiscalDateEnding + 75 days (a conservative US 10-Q filing lag). `period`
# = fiscal quarter as year*100+Q (qlib PIT convention). Needs the $49.99 AV tier
# (75 req/min, no daily cap); ~3 calls/symbol -> full S&P500 in ~30 min.
import sys
from pathlib import Path
from typing import Iterable, Optional

import fire
import pandas as pd
from loguru import logger

CUR_DIR = Path(__file__).resolve().parent
sys.path.append(str(CUR_DIR.parent.parent))
from data_collector.base import BaseNormalize, BaseRun  # noqa: E402
from data_collector.alpha_vantage.collector import AlphaVantageCollector  # noqa: E402

# AV statement key -> our PIT field name (lowercase, `_q` = quarterly, matches CN PIT style)
_INCOME = {"totalRevenue": "revenue_q", "grossProfit": "grossprofit_q", "netIncome": "netincome_q"}
_BALANCE = {
    "totalShareholderEquity": "equity_q",
    "totalAssets": "assets_q",
    "commonStockSharesOutstanding": "shares_q",
}
_FILING_LAG_DAYS = 75  # fallback PIT date when a statement quarter has no matching earnings reportedDate
_MISSING = {None, "None", "none", "", "-"}


def _period(fiscal_date: str) -> int:
    """'2019-03-31' -> 201901 (year*100 + quarter), qlib PIT period encoding."""
    d = pd.Timestamp(fiscal_date)
    return d.year * 100 + (d.month - 1) // 3 + 1


class AVFundamentalsCollector(AlphaVantageCollector):
    def get_data(self, symbol: str, interval: str, start_datetime, end_datetime) -> pd.DataFrame:
        rows = []
        reported = {}  # fiscalDateEnding -> reportedDate (the PIT announcement date)

        earn = self._get({"function": "EARNINGS", "symbol": symbol})
        for e in earn.get("quarterlyEarnings", []) or []:
            fd, rd, eps = e.get("fiscalDateEnding"), e.get("reportedDate"), e.get("reportedEPS")
            if not fd:
                continue
            if rd:
                reported[fd] = rd
            if rd and eps not in _MISSING:
                rows.append((rd, _period(fd), "eps_q", eps))

        def _add(reports, mapping):
            for r in reports or []:
                fd = r.get("fiscalDateEnding")
                if not fd:
                    continue
                date = reported.get(fd) or (pd.Timestamp(fd) + pd.Timedelta(days=_FILING_LAG_DAYS)).strftime("%Y-%m-%d")
                per = _period(fd)
                for av_key, field in mapping.items():
                    v = r.get(av_key)
                    if v not in _MISSING:
                        rows.append((date, per, field, v))

        _add(self._get({"function": "INCOME_STATEMENT", "symbol": symbol}).get("quarterlyReports"), _INCOME)
        _add(self._get({"function": "BALANCE_SHEET", "symbol": symbol}).get("quarterlyReports"), _BALANCE)

        if not rows:
            logger.warning(f"{symbol}: no fundamentals")
            return pd.DataFrame()
        df = pd.DataFrame(rows, columns=["date", "period", "field", "value"])
        df["symbol"] = self.normalize_symbol(symbol)
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        df = df.dropna(subset=["value"])
        m = (pd.to_datetime(df["date"]) >= pd.Timestamp(start_datetime)) & (
            pd.to_datetime(df["date"]) <= pd.Timestamp(end_datetime)
        )
        return df[m].reset_index(drop=True)


class AVFundamentalsNormalize(BaseNormalize):
    def _get_calendar_list(self) -> Optional[Iterable[pd.Timestamp]]:
        return None

    def normalize(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df
        df = df.copy()
        df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
        df["period"] = pd.to_numeric(df["period"], errors="coerce").astype("Int64")
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        df = df.dropna(subset=["period", "value"])
        # one value per (field, period): keep the EARLIEST announcement (true first availability)
        df = df.sort_values("date").drop_duplicates(subset=["field", "period"], keep="first")
        return df[["date", "period", "field", "value"]].sort_values(["field", "period"]).reset_index(drop=True)


class Run(BaseRun):
    def __init__(self, source_dir=None, normalize_dir=None, max_workers=1, interval="quarterly"):
        super().__init__(source_dir=source_dir, normalize_dir=normalize_dir, max_workers=max_workers, interval=interval)
        self._cur_module = sys.modules[__name__]  # BaseRun hardcodes import_module("collector"); point it here

    @property
    def collector_class_name(self):
        return "AVFundamentalsCollector"

    @property
    def normalize_class_name(self):
        return "AVFundamentalsNormalize"

    @property
    def default_base_dir(self):
        return CUR_DIR.joinpath("av_fund_data")


if __name__ == "__main__":
    fire.Fire(Run)
