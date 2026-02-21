import numpy as np
import pandas as pd

def max_drawdown(prices):
    """
    计算最大回撤
    Logic: (price / price.cummax() - 1).min()
    """
    if isinstance(prices, pd.Series):
        values = prices.values
    else:
        values = prices
        
    cummax = np.maximum.accumulate(values)
    drawdowns = (values - cummax) / cummax
    return drawdowns.min()

def max_drawdown_details(prices: pd.Series):
    """
    返回最大回撤及其发生的日期和金额 (mdd_pct, mdd_amount, peak_date, valley_date)
    """
    if prices.empty:
        return 0.0, 0.0, None, None, 0.0, 0.0
        
    cummax = prices.cummax()
    drawdowns = (prices - cummax) / cummax
    mdd = drawdowns.min()
    
    if mdd == 0:
        return 0.0, 0.0, prices.index[0], prices.index[0], prices.iloc[0], prices.iloc[0]
        
    valley_date = drawdowns.idxmin()
    peak_date = prices[:valley_date].idxmax()
    
    peak_price = prices[peak_date]
    valley_price = prices[valley_date]
    mdd_amount = valley_price - peak_price
    
    return mdd, mdd_amount, peak_date, valley_date, peak_price, valley_price

def recovery_details(prices: pd.Series):
    """
    返回恢复时间详情 (days, recovery_end_date)
    """
    if not isinstance(prices, pd.Series) or prices.empty:
        return None, None
    
    cummax = prices.cummax()
    drawdowns = (prices - cummax) / cummax
    mdd_val = drawdowns.min()
    
    if mdd_val == 0:
        return 0, None
        
    valley_date = drawdowns.idxmin()
    peak_date = prices[:valley_date].idxmax()
    peak_price = prices[peak_date]
    
    post_valley = prices[valley_date:]
    recovery_dates = post_valley[post_valley >= peak_price].index
    
    if len(recovery_dates) > 0:
        recovery_end_date = recovery_dates[0]
        days = (recovery_end_date - valley_date).days
        return days, recovery_end_date
    else:
        return None, None

def recovery_progress(prices: pd.Series):
    """
    计算修复进度
    Logic: (current_price - valley_price) / (peak_price - valley_price)
    """
    if not isinstance(prices, pd.Series) or prices.empty:
        return 0.0
        
    cummax = prices.cummax()
    drawdowns = (prices - cummax) / cummax
    mdd_val = drawdowns.min()
    
    if mdd_val == 0:
        return 1.0 # No drawdown means fully recovered/at peak
        
    valley_date = drawdowns.idxmin()
    peak_date = prices[:valley_date].idxmax()
    
    peak_price = prices[peak_date]
    valley_price = prices[valley_date]
    current_price = prices.iloc[-1]
    
    # Avoid division by zero
    if peak_price == valley_price:
        return 1.0
        
    progress = (current_price - valley_price) / (peak_price - valley_price)
    return progress

def current_drawdown(prices):
    """
    计算当前回撤
    Logic: price[-1] / price.max() - 1
    """
    if isinstance(prices, pd.Series):
        values = prices.values
    else:
        values = prices
        
    if len(values) == 0:
        return 0.0
        
    return values[-1] / values.max() - 1

def recovery_time(prices):
    """
    计算恢复时间 (天数)
    Logic: 从最大回撤谷底回到前高所需天数
    Need pandas Series with DatetimeIndex for accurate day count
    """
    if not isinstance(prices, pd.Series):
        # Fallback to index count if simple array
        return None
    
    # 1. Find Max Drawdown Valley Date
    cummax = prices.cummax()
    drawdowns = (prices - cummax) / cummax
    mdd_val = drawdowns.min()
    
    if mdd_val == 0:
        return 0
        
    # Find the date of the max drawdown (valley)
    valley_date = drawdowns.idxmin()
    
    # 2. Find the Peak Date *before* the Valley
    # The peak is the max price up to the valley date
    peak_date = prices[:valley_date].idxmax()
    peak_price = prices[peak_date]
    
    # 3. Find recovery date (first date after valley where price >= peak_price)
    post_valley = prices[valley_date:]
    recovery_dates = post_valley[post_valley >= peak_price].index
    
    if len(recovery_dates) > 0:
        recovery_date = recovery_dates[0]
        return (recovery_date - valley_date).days
    else:
        return None  # Not recovered yet
