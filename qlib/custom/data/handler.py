# [FORK] First custom factor handler for this fork (FORK.md §10 Phase 3).
#
# WHAT: `Alpha158Custom` = upstream Alpha158 (158 price/volume features) PLUS a small,
#       curated set of OUR OWN, economically-motivated factors that are NOT already in
#       Alpha158. This is the reference example of the fork's extension mechanism:
#       a new class under `qlib/custom/`, referenced from a workflow YAML via
#       `module_path: qlib.custom.data.handler` — zero edits to upstream files.
#
# WHY these factors (each has a published economic thesis and is DISTINCT from Alpha158,
# which already covers intraday kbar shape (KMID/KUP/...), close-based STD/MA/ROC, and
# price-level rolling MAX/MIN over windows ≤60):
#
#   OVERNIGHT  open/prev_close-1 .... overnight vs intraday return drift (Lou/Polk/Skouras
#                                     2019). Alpha158 has intraday (KMID) but NOT overnight.
#   MOM12_1    12m return skip last  . Jegadeesh-Titman (1993) momentum, skipping the most
#                                     recent month to avoid 1m reversal. Alpha158 ROC tops
#                                     out at 60d with no skip-month.
#   HI52W      close / 252d-high .... George-Hwang (2004) 52-week-high momentum. Alpha158's
#                                     MAX is high-based over ≤60d; the 252d horizon is the
#                                     economic content here.
#   LOTTERY21  max daily return 21d . Bali-Cakici-Whitelaw (2011) MAX / lottery demand —
#                                     a NEGATIVE predictor. Alpha158's MAX is a price level,
#                                     not a max daily RETURN.
#   AMIHUD21   mean(|ret|/$vol) 21d . Amihud (2002) illiquidity premium. Alpha158 has no
#                                     dollar-volume illiquidity measure.
#   PVOL21     std(log(hi/lo)) 21d .. Parkinson (1980) range volatility -> low-volatility
#                                     anomaly. Alpha158 STD is close-to-close only.
#
# All expressions use only fields present in our Massive/AV dumps
# (open/high/low/close/volume/vwap/change). `change` = daily pct return column.

from qlib.contrib.data.handler import Alpha158


class Alpha158Custom(Alpha158):
    """Alpha158 + this fork's curated custom factors.

    Drop-in replacement for Alpha158 in any workflow YAML; same kwargs. The only
    difference is `get_feature_config()` appends the factors defined in
    `get_custom_feature_config()`. Override that method (or subclass) to iterate
    on your own alpha ideas — this is the per-idea research seam.
    """

    @staticmethod
    def get_custom_feature_config():
        """Return (fields, names) for our custom factors. Edit here to add ideas."""
        fields = [
            "$open/Ref($close, 1) - 1",  # OVERNIGHT
            "Ref($close, 21)/Ref($close, 252) - 1",  # MOM12_1
            "$close/Max($close, 252)",  # HI52W
            "Max($change, 21)",  # LOTTERY21
            "Mean(Abs($change)/($close*$volume+1e-12), 21)",  # AMIHUD21
            "Std(Log($high/$low), 21)",  # PVOL21
        ]
        names = ["OVERNIGHT", "MOM12_1", "HI52W", "LOTTERY21", "AMIHUD21", "PVOL21"]
        return fields, names

    def get_feature_config(self):
        base_fields, base_names = super().get_feature_config()
        cust_fields, cust_names = self.get_custom_feature_config()
        return base_fields + cust_fields, base_names + cust_names


class Alpha158CustomLite(Alpha158Custom):
    """Pruned `Alpha158Custom`: only the factors that survived IC attribution.

    `examples/fork/factor_ic_attribution.py` (test 2021-2026, market=all) showed that
    of the 6 custom factors only the momentum pair and illiquidity carry reliable
    signal, while PVOL21 / LOTTERY21 / OVERNIGHT were noise (|t|<1.3). Dropping the
    noise factors aims to keep the excess return while reducing drawdown. Kept:
        MOM12_1   RankIC +0.018  t=+3.0   (winner)
        HI52W     RankIC +0.012  t=+1.8   (momentum family)
        AMIHUD21  RankIC -0.010  t=-2.1   (significant; LightGBM uses the negative sign)
    """

    @staticmethod
    def get_custom_feature_config():
        fields = [
            "Ref($close, 21)/Ref($close, 252) - 1",  # MOM12_1
            "$close/Max($close, 252)",  # HI52W
            "Mean(Abs($change)/($close*$volume+1e-12), 21)",  # AMIHUD21
        ]
        names = ["MOM12_1", "HI52W", "AMIHUD21"]
        return fields, names


class Alpha158Custom5(Alpha158Custom):
    """`Alpha158Custom` minus LOTTERY21 — pruned by gain/SHAP attribution.

    Unlike the IC-pruned `Alpha158CustomLite` (which backfired, FORK.md §9.7), this drops
    ONLY the factor that ranked bottom by BOTH LightGBM gain (#86/164) and TreeSHAP
    (#49/164) — LOTTERY21 (FORK.md §9.8). PVOL21/OVERNIGHT are kept here because, despite
    weak univariate IC, the model uses them heavily for interactions (PVOL21 is gain-rank
    #3). This tests whether gain/SHAP-guided pruning beats IC-guided pruning.
    """

    @staticmethod
    def get_custom_feature_config():
        fields = [
            "$open/Ref($close, 1) - 1",  # OVERNIGHT
            "Ref($close, 21)/Ref($close, 252) - 1",  # MOM12_1
            "$close/Max($close, 252)",  # HI52W
            "Mean(Abs($change)/($close*$volume+1e-12), 21)",  # AMIHUD21
            "Std(Log($high/$low), 21)",  # PVOL21
        ]
        names = ["OVERNIGHT", "MOM12_1", "HI52W", "AMIHUD21", "PVOL21"]
        return fields, names
