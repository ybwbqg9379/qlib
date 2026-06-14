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
