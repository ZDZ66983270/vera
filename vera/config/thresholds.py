# vera/config/thresholds.py

UNDERLYING = {
    "discovery": {
        "daily_drop_pct": -0.06,
        "ret_z": -2.0,
        "vol_ratio": 1.5,
        "close_pos": 0.35
    },
    "stabilization": {
        "vol_ratio_max": 1.5
    },
    "reversal": {
        "min_days_no_new_low": 2,
        "close_pos": 0.55
    }
}

OPTIONS = {
    "iv_down_days": 2,
    "min_dte": 60
}

VOL_ANNUALIZATION_DAYS = 252
