import numpy as np
import pandas as pd

def value_at_risk(returns, confidence=0.95):
    """计算 VaR"""
    return np.percentile(returns, (1 - confidence) * 100)

def worst_n_day_drop(prices, window=5):
    """
    最差 n 日跌幅
    Logic: 滚动 n 日收益率的最小值
    """
    if isinstance(prices, pd.Series):
        # 使用 pct_change(window) 直接计算 n 日收益率
        rolling_returns = prices.pct_change(periods=window)
        return rolling_returns.min()
    else:
        # Numpy array fallback (less efficient/accurate for simple returns accumulation without loop)
        # Using approximation: sum of log returns or strictly:
        # For numpy, strictly: (p[t] - p[t-n]) / p[t-n]
        # p[n:] / p[:-n] - 1
        values = prices
        if len(values) <= window:
            return 0.0
        
        # Vectorized n-day return
        ret_n = values[window:] / values[:-window] - 1
        return ret_n.min()
