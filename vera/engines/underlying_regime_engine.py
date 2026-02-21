# vera/engines/underlying_regime_engine.py

import pandas as pd
from vera.utils.indicators import close_position, vol_ratio, is_new_low, ret_zscore
from vera.config.thresholds import UNDERLYING

class UnderlyingRegimeEngine:
    """
    输出 U_state:
    U1 = Uptrend
    U2 = Range
    U3 = Discovery (Price Discovery / Breakdown)
    U4 = Stabilization
    U5 = Reversal
    """

    def evaluate(self, df: pd.DataFrame) -> dict:
        """
        df: 日线 DataFrame，至少包含
        ['open','high','low','close','volume','vol_ma20','ret']
        """
        # Ensure df has enough data
        if len(df) < 60:
            return {"U_state": "UNKNOWN", "reason": "Insufficient data"}
            
        last = df.iloc[-1]

        # Calculate Indicators
        # Note: Some indicators might need the full series or a window
        cp = close_position(last)
        vr = vol_ratio(last["volume"], last.get("vol_ma20", 0)) # Safe get
        new_low = is_new_low(df["low"], df["close"])
        rz = ret_zscore(df["log_ret"])

        # Discovery Logic (U3)
        discovery_hits = 0
        if last["log_ret"] <= UNDERLYING["discovery"]["daily_drop_pct"]:
            discovery_hits += 1
        if rz <= UNDERLYING["discovery"]["ret_z"]:
            discovery_hits += 1
        if vr >= UNDERLYING["discovery"]["vol_ratio"]:
            discovery_hits += 1
        if cp <= UNDERLYING["discovery"]["close_pos"]:
            discovery_hits += 1
        if new_low:
            discovery_hits += 1

        state = "U2_RANGE" # Default
        
        # State Determination
        if discovery_hits >= 3:
            state = "U3_DISCOVERY"
        elif not new_low and vr < UNDERLYING["stabilization"]["vol_ratio_max"]:
            # Potential U4 or U5
            # U5 criteria: close_pos >= threshold
            if cp >= UNDERLYING["reversal"]["close_pos"]:
                 state = "U5_REVERSAL"
            else:
                 state = "U4_STABILIZATION"
        else:
            state = "U2_RANGE"

        return {
            "U_state": state,
            "metrics": {
                "close_pos": cp,
                "vol_ratio": vr,
                "new_low": new_low,
                "ret_z": rz,
                "daily_ret": last.get("ret", 0.0), # Use simple return for UI display
                "discovery_hits": discovery_hits
            }
        }
