# [FORK] Custom factor handlers for this fork (FORK.md §10 Phase 3).
#
# WHAT: `Alpha158Custom` = upstream Alpha158 (158 price/volume features) PLUS a curated
#       set of OUR OWN, economically-motivated factors, defined in the CUSTOM_FACTORS
#       registry below. Handler variants (`Alpha158Custom5`, `Alpha158CustomLite`) just
#       pick a SUBSET of the registry by name. Referenced from workflow YAML via
#       `module_path: qlib.custom.data.handler` — zero edits to upstream files.
#
# WHY a registry: a single {name: (expr, thesis)} dict means adding a factor is one entry
#       and a handler variant is one name-list — no duplicated expression strings. It is
#       also the seam for the §10.0 end goal (LLM / RD-Agent auto-mined factors): a dict
#       is far easier to generate/extend programmatically than scattered string lists.
#
# Each factor below is DISTINCT from Alpha158 (which already covers intraday kbar shape
# (KMID/KUP/...), close-based STD/MA/ROC, and price-level rolling MAX/MIN over windows
# <=60) and carries a published economic thesis. All expressions use only fields present
# in our Massive/AV dumps (open/high/low/close/volume/vwap/change; `change` = daily ret).
#
# Single-factor IC + gain/SHAP attribution and multi-seed / walk-forward robustness for
# these factors are recorded in FORK.md §9.6-9.11.

from qlib.contrib.data.handler import Alpha158

# name -> (expression, one-line economic thesis). Order here = default feature order.
CUSTOM_FACTORS = {
    "OVERNIGHT": (
        "$open/Ref($close, 1) - 1",
        "overnight gap return (Lou/Polk/Skouras 2019); Alpha158 has intraday, not this",
    ),
    "MOM12_1": (
        "Ref($close, 21)/Ref($close, 252) - 1",
        "Jegadeesh-Titman (1993) 12-1 momentum, skip last month; Alpha158 ROC tops at 60d",
    ),
    "HI52W": ("$close/Max($close, 252)", "George-Hwang (2004) 52-week-high momentum; the 252d horizon is the content"),
    "LOTTERY21": ("Max($change, 21)", "Bali-Cakici-Whitelaw (2011) MAX / lottery demand (negative predictor)"),
    "AMIHUD21": (
        "Mean(Abs($change)/($close*$volume+1e-12), 21)",
        "Amihud (2002) illiquidity; Alpha158 has no dollar-volume measure",
    ),
    "PVOL21": (
        "Std(Log($high/$low), 21)",
        "Parkinson (1980) range volatility -> low-vol anomaly; Alpha158 STD is close-only",
    ),
}


# Fundamental value/quality factors — the §9.11 non-momentum diversifiers. These read
# point-in-time Alpha Vantage data (FORK.md §9.14) via the PIT operator P($$<field>),
# so a backtest never sees a number before its earnings reportedDate. Quarterly fields
# get a `_q` suffix at dump time -> `eps_q` becomes `$$eps_q_q`. Available only on the
# Massive dataset with PIT dumped (us_data_massive/financial/); on price-only datasets
# these are NaN and get filled by Alpha158's infer processors.
FUND_FACTORS = {
    # value: cheap stocks (high yield / high book-to-market) tend to outperform
    "EY_TTM": (
        "P($$eps_q_q + Ref($$eps_q_q, 1) + Ref($$eps_q_q, 2) + Ref($$eps_q_q, 3))/$close",
        "trailing-12m earnings yield (value)",
    ),
    "BM": ("P($$equity_q_q)/($close*P($$shares_q_q)+1e-12)", "book-to-market (Fama-French value)"),
    # quality: profitable / efficient firms tend to outperform (Novy-Marx, Fama-French)
    "ROE": ("P($$netincome_q_q)/(P($$equity_q_q)+1e-12)", "return on equity (quality)"),
    "GPOA": ("P($$grossprofit_q_q)/(P($$assets_q_q)+1e-12)", "gross profits / assets (Novy-Marx 2013 quality)"),
    "GMARGIN": ("P($$grossprofit_q_q)/(P($$revenue_q_q)+1e-12)", "gross margin (quality)"),
    # growth: year-over-year sales growth (PIT Ref by 4 quarters = 1y ago, past-only)
    "SALESGRWTH": ("P($$revenue_q_q)/(P(Ref($$revenue_q_q, 4))+1e-12) - 1", "YoY revenue growth"),
}


def select_factors(names, registry=CUSTOM_FACTORS):
    """Return (fields, names) for the given registry factor names, in that order."""
    return [registry[n][0] for n in names], list(names)


class Alpha158Custom(Alpha158):
    """Alpha158 + this fork's curated custom factors.

    Drop-in replacement for Alpha158 in any workflow YAML; same kwargs. `FACTORS` lists
    which registry factors to append — subclass and override it (or edit CUSTOM_FACTORS)
    to iterate on alpha ideas. This is the per-idea research seam.
    """

    FACTORS = list(CUSTOM_FACTORS)  # all 6

    @classmethod
    def get_custom_feature_config(cls):
        return select_factors(cls.FACTORS)

    def get_feature_config(self):
        base_fields, base_names = super().get_feature_config()
        cust_fields, cust_names = self.get_custom_feature_config()
        return base_fields + cust_fields, base_names + cust_names


class Alpha158Custom5(Alpha158Custom):
    """`Alpha158Custom` minus LOTTERY21 — pruned by gain/SHAP attribution (FORK.md §9.8-9.11).

    Drops ONLY the factor that ranked bottom by both LightGBM gain (#86/164) and TreeSHAP
    (#49/164). Multi-seed (§9.10) found it tied with the 6-factor version but lower-variance,
    so it is the default handler. PVOL21/OVERNIGHT are kept despite weak univariate IC
    because the model uses them for interactions (PVOL21 is gain-rank #3).
    """

    FACTORS = ["OVERNIGHT", "MOM12_1", "HI52W", "AMIHUD21", "PVOL21"]


class Alpha158CustomLite(Alpha158Custom):
    """IC-pruned variant kept ONLY as a documented negative result (FORK.md §9.7).

    Drops the 3 factors weak by univariate IC — which BACKFIRED (excess +5.7%->+0.4%):
    univariate IC is the wrong tool for pruning a nonlinear tree model. Do not use; see
    Alpha158Custom5 for the correct gain/SHAP-based pruning.
    """

    FACTORS = ["MOM12_1", "HI52W", "AMIHUD21"]


class Alpha158CustomFund(Alpha158Custom5):
    """Alpha158Custom5 (price) PLUS point-in-time fundamental value/quality/growth factors.

    Tests the §9.11 hypothesis: the strategy is regime-dependent because its signal is
    momentum-heavy (price/volume only); adding orthogonal value/quality factors from
    fundamentals (FORK.md §9.14) should diversify the regime risk — especially the
    2017-2019 smooth-large-cap-bull losing streak where momentum lagged. Requires the
    Massive dataset with PIT dumped; FUND_FACTORS are NaN-and-filled elsewhere.
    """

    FUND = list(FUND_FACTORS)  # EY_TTM, BM, ROE, GPOA, GMARGIN, SALESGRWTH

    def get_feature_config(self):
        base_fields, base_names = super().get_feature_config()  # Alpha158 + 5 price factors
        fund_fields, fund_names = select_factors(self.FUND, FUND_FACTORS)
        return base_fields + fund_fields, base_names + fund_names
