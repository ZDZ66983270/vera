import numpy as np
from config import TRADING_DAYS

def annual_volatility(returns):
    """计算年化波动率"""
    if len(returns) < 2:
        return 0.0
    return np.std(returns) * np.sqrt(TRADING_DAYS)
