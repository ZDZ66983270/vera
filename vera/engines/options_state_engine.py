# vera/engines/options_state_engine.py

import pandas as pd
from vera.config.thresholds import OPTIONS

class OptionsStateEngine:
    """
    O_state:
    O1 = IV_EXPANSION
    O2 = IV_PLATEAU
    O3 = IV_CRUSH
    """

    def evaluate(self, vol_series: pd.Series, source: str = "real_iv") -> dict:
        """
        vol_series: IV history (daily) OR realized volatility proxy
        source: "real_iv" or "proxy_hv20"
        
        # 如果使用 hv20_annualized 作为 proxy：
        # O1: realized vol 短期放大 → 市场处于高波动/恐慌区
        # O3: realized vol 在高位后逐步回落 → 风险释放后进入收敛阶段
        """
        window = OPTIONS["iv_down_days"] + 1
        # Data sufficiency check
        if len(vol_series) < window:
             return {
                 "O_state": "O2_PLATEAU", 
                 "reason": "Insufficient Vol data",
                 "vol_source": source
             }

        recent = vol_series.iloc[-window:]

        # IV Crush: continuously decreasing for N days
        # diff() of [t-2, t-1, t] -> [NaN, (t-1)-(t-2), t-(t-1)]
        # We need the last N diffs to be negative.
        diffs = recent.diff().iloc[1:] # Drop first NaN
        
        if all(diffs < 0):
            state = "O3_IV_CRUSH"
        elif recent.iloc[-1] > recent.iloc[-2]:
            state = "O1_IV_EXPANSION"
        else:
            state = "O2_PLATEAU"
            
        # Tolerance logic for Proxy
        warning_msg = ""
        if source.startswith("proxy"):
             warning_msg = "Signal based on realized volatility proxy; reference only."

        return {
            "O_state": state,
            "iv_now": float(recent.iloc[-1]),
            "iv_now_pct": float(recent.iloc[-1] * 100.0),
            "vol_source": source,
            "warning": warning_msg,
            "metrics": {
                "iv_today": recent.iloc[-1],
                "iv_prev": recent.iloc[-2],
                "iv_change": recent.iloc[-1] - recent.iloc[-2]
            }
        }
