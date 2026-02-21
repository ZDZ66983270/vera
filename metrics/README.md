from metrics.drawdown import max_drawdown, current_drawdown, recovery_time
from metrics.volatility import annual_volatility
from metrics.tail_risk import worst_n_day_drop
import pandas as pd

class RiskEngine:
    @staticmethod
    def calculate_risk_metrics(prices: pd.Series):
        """
        风险计算引擎
        Input: adj_close series (pandas Series)
        Output: Risk Metrics Set (dict)
        """
        if prices.empty:
            return {}
            
        # Ensure we are working with a Series for date operations
        if not isinstance(prices, pd.Series):
            raise ValueError("RiskEngine requires a pandas Series with DatetimeIndex")

        # Returns for volatility
        returns = prices.pct_change().dropna()
        
        metrics = {
            "max_drawdown": max_drawdown(prices),          # 最大回撤
            "current_drawdown": current_drawdown(prices),  # 当前回撤
            "annual_volatility": annual_volatility(returns), # 年化波动率
            "recovery_time": recovery_time(prices),        # 恢复时间
            "worst_5d_drop": worst_n_day_drop(prices, window=5) # 最差5日跌幅
        }
        
        return metrics
