# [FORK] Unit tests for our self-built US-equity collectors (FORK.md §5.3).
#
# Until now collector correctness was only asserted by manual smoke tests recorded in
# FORK.md §9. These pin the data-correctness core (symbol parsing, OHLC parsing/renaming,
# the `factor`/`change` normalize conventions, and the new bounded-retry logic) so an
# upstream merge or a vendor API change can't silently break them. No network calls:
# the HTTP session is mocked.
import os
import sys
from pathlib import Path

import pandas as pd
import pytest

SCRIPTS = Path(__file__).resolve().parents[1].joinpath("scripts")
sys.path.append(str(SCRIPTS))
sys.path.append(str(SCRIPTS.joinpath("data_collector")))

os.environ.setdefault("MASSIVE_API_KEY", "test-key")  # collectors read a key at import/init
os.environ.setdefault("ALPHA_VANTAGE_API_KEY", "test-key")

from data_collector.massive import collector as mc  # noqa: E402
from data_collector.alpha_vantage import collector as av  # noqa: E402
from data_collector.alpha_vantage import fundamentals as avf  # noqa: E402


class _Resp:
    """Minimal stand-in for requests.Response."""

    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise mc.requests.HTTPError(str(self.status_code))


# --------------------------------------------------------------------------- #
# shared symbol parsing
# --------------------------------------------------------------------------- #
def test_read_symbols_forms(tmp_path):
    assert mc._read_symbols("AAPL,msft, SPY ") == ["AAPL", "msft", "SPY"]
    assert mc._read_symbols(["aapl", " ", "MSFT"]) == ["aapl", "MSFT"]
    assert mc._read_symbols(None) == ["AAPL", "MSFT", "SPY"]  # smoke default
    f = tmp_path / "inst.txt"
    f.write_text("AAPL\t2010-01-01\t2020-01-01\nMSFT\t2010-01-01\t2020-01-01\nAAPL\textra\n")
    assert mc._read_symbols(str(f)) == ["AAPL", "MSFT"]  # tab-sep instrument file, deduped+sorted


def test_av_months_inclusive():
    assert av._months(pd.Timestamp("2023-11-15"), pd.Timestamp("2024-02-03")) == [
        "2023-11",
        "2023-12",
        "2024-01",
        "2024-02",
    ]


# --------------------------------------------------------------------------- #
# Massive: get_data parsing + pagination + bounded retry
# --------------------------------------------------------------------------- #
def _massive_collector():
    c = object.__new__(mc.MassiveCollector)  # bypass heavy BaseCollector.__init__
    c._adjusted = True
    c._key = "test-key"
    c._base = "https://api.massive.com"
    return c


def test_massive_get_data_parsing_and_pagination(monkeypatch):
    c = _massive_collector()
    page1 = {
        "results": [{"t": 1514812200000, "o": 1.0, "h": 2.0, "l": 0.5, "c": 1.5, "v": 100, "vw": 1.4}],
        "next_url": "https://api.massive.com/next",
    }
    page2 = {"results": [{"t": 1514898600000, "o": 1.5, "h": 2.5, "l": 1.0, "c": 2.0, "v": 200, "vw": 1.9}]}
    pages = iter([_Resp(page1), _Resp(page2)])
    c._session = type("S", (), {"get": lambda self, url, timeout=30: next(pages)})()

    df = c.get_data("aapl", "1d", pd.Timestamp("2018-01-01"), pd.Timestamp("2018-01-02"))
    assert list(df.columns) == ["symbol", "date", "open", "high", "low", "close", "volume", "vwap"]
    assert len(df) == 2  # both pages concatenated
    assert (df["symbol"] == "AAPL").all()  # normalized upper
    assert df.iloc[0]["close"] == 1.5 and df.iloc[0]["vwap"] == 1.4  # c->close, vw->vwap


def test_massive_fetch_retries_then_skips(monkeypatch):
    c = _massive_collector()
    c.MAX_RETRIES = 3
    monkeypatch.setattr(mc.time, "sleep", lambda *_: None)  # don't actually wait
    calls = {"n": 0}

    def always_429(self, url, timeout=30):
        calls["n"] += 1
        return _Resp({}, status=429)

    c._session = type("S", (), {"get": always_429})()
    df = c.get_data("AAPL", "1d", pd.Timestamp("2018-01-01"), pd.Timestamp("2018-01-02"))
    assert df.empty  # persistent 429 -> bounded retries -> symbol skipped, no hang/crash
    assert calls["n"] == 3  # exactly MAX_RETRIES attempts, not infinite


# --------------------------------------------------------------------------- #
# normalize: the factor / change conventions (the part most likely to silently break)
# --------------------------------------------------------------------------- #
def test_massive_normalize_factor_and_change():
    n = mc.MassiveNormalize()
    raw = pd.DataFrame(
        {
            "date": ["2020-01-03", "2020-01-02", "2020-01-02"],  # unsorted + a duplicate
            "open": [10, 9, 9],
            "high": [11, 10, 10],
            "low": [9, 8, 8],
            "close": [10.0, 9.0, 9.0],
            "volume": [100, 90, 90],
            "vwap": [10, 9, 9],
        }
    )
    out = n.normalize(raw)
    assert list(out["date"].astype(str)) == ["2020-01-02", "2020-01-03"]  # deduped + sorted
    assert (out["factor"] == 1.0).all()  # Massive prices already adjusted -> factor 1
    assert out["change"].iloc[0] != out["change"].iloc[0] or pd.isna(out["change"].iloc[0])  # first NaN
    assert out["change"].iloc[1] == pytest.approx((10.0 - 9.0) / 9.0)  # pct_change


def test_fundamentals_period_encoding():
    # year*100 + quarter (qlib PIT convention); quarter from the fiscal-date-ending month
    assert avf._period("2019-03-31") == 201901
    assert avf._period("2019-06-30") == 201902
    assert avf._period("2019-12-31") == 201904
    assert avf._period("2020-09-30") == 202003


def test_fundamentals_normalize_pit_dedup():
    n = avf.AVFundamentalsNormalize()
    # same (field, period) reported twice (restatement) -> keep the EARLIEST date (first availability)
    raw = pd.DataFrame(
        {
            "date": ["2020-05-01", "2020-02-01", "2020-02-01"],
            "period": [202001, 201904, 201904],
            "field": ["eps_q", "eps_q", "eps_q"],
            "value": [1.1, 0.9, 0.9],
            "symbol": ["AAPL", "AAPL", "AAPL"],
        }
    )
    out = n.normalize(raw)
    assert list(out.columns) == ["date", "period", "field", "value"]  # symbol dropped for dump_pit
    assert len(out) == 2  # duplicate (eps_q, 201904) collapsed
    row = out[out["period"] == 201904].iloc[0]
    assert row["date"] == "2020-02-01"  # earliest kept


def test_av_normalize_factor_from_adjclose():
    n = av.AlphaVantageNormalize()
    raw = pd.DataFrame(
        {
            "date": ["2020-01-02", "2020-01-03"],
            "open": [10, 11],
            "high": [12, 13],
            "low": [9, 10],
            "close": [10.0, 20.0],
            "adjclose": [5.0, 10.0],  # 0.5x of raw -> factor 0.5
            "volume": [100, 200],
        }
    )
    out = n.normalize(raw)
    assert "adjclose" not in out.columns  # consumed
    assert out["factor"].iloc[0] == pytest.approx(0.5)  # adjclose/close
    assert out["change"].iloc[1] == pytest.approx((20.0 - 10.0) / 10.0)
