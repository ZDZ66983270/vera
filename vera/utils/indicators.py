# vera/utils/indicators.py

import pandas as pd
import numpy as np

def close_position(row):
    if row["high"] == row["low"]:
        return 0.5
    return (row["close"] - row["low"]) / (row["high"] - row["low"])

def vol_ratio(volume, vol_ma):
    return volume / vol_ma if vol_ma > 0 else np.nan

def is_new_low(low_series: pd.Series, close_series: pd.Series = None, window=3):
    if len(low_series) < window:
        return False
        
    # Condition 1: Current low is lower than previous N-1 lows
    new_low_hit = low_series.iloc[-1] < low_series.iloc[-window:-1].min()
    
    # Condition 2: Current close is lower than previous N-1 closes (if provided)
    if close_series is not None:
        new_close_hit = close_series.iloc[-1] < close_series.iloc[-window:-1].min()
        return new_low_hit or new_close_hit
        
    return new_low_hit

def ret_zscore(returns: pd.Series, window=60):
    if len(returns) < window:
        return 0
    mu = returns.iloc[-window:].mean()
    sigma = returns.iloc[-window:].std()
    if sigma == 0:
        return 0
    return (returns.iloc[-1] - mu) / sigma

def annualized_volatility(returns: pd.Series, window=20):
    """Calculates annualized historical volatility."""
    if len(returns) < window:
        return 0.25 # Fallback to placeholder if not enough data
    # Standard deviation of returns * sqrt(252 trading days)
    sigma = returns.iloc[-window:].std()
    return sigma * np.sqrt(252)
