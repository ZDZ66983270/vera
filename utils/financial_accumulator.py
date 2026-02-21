"""
财报累计值转换引擎
将半年报、前三季度等累计值转换为单季度数据
"""

from typing import Dict, Optional, Any
import sqlite3


class FinancialAccumulator:
    """财报累计值转换引擎"""
    
    # 流量指标（需要转换）
    FLOW_METRICS = {
        'revenue', 'net_profit', 'net_interest_income', 
        'net_fee_income', 'provision_expense',
        'operating_cashflow', 'dividends_paid'
    }
    
    # 存量指标（不需要转换）
    STOCK_METRICS = {
        'total_assets', 'total_liabilities', 'total_loans',
        'cash_and_equivalents', 'total_debt', 'npl_ratio',
        'loan_loss_allowance', 'provision_coverage', 'core_tier1_ratio'
    }
    
    def convert_to_quarterly(self, db_conn: sqlite3.Connection, asset_id: str, 
                            report_date: str, cumulative_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        将累计值转换为单季度
        
        Args:
            db_conn: 数据库连接
            asset_id: 资产ID
            report_date: 报告日期 (YYYY-MM-DD)
            cumulative_data: 累计数据
            
        Returns:
            Dict: 单季度数据
        """
        month_day = report_date[5:]
        year = report_date[:4]
        
        if month_day == "03-31":
            # Q1本身是单季
            return cumulative_data
        
        elif month_day == "06-30":
            # H1 - Q1
            q1_date = f"{year}-03-31"
            q1_data = self._query_quarter(db_conn, asset_id, q1_date)
            return self._subtract(cumulative_data, q1_data)
        
        elif month_day == "09-30":
            # 9M - H1
            h1_date = f"{year}-06-30"
            h1_data = self._query_quarter(db_conn, asset_id, h1_date)
            return self._subtract(cumulative_data, h1_data)
        
        elif month_day == "12-31":
            # FY - 9M
            q3_date = f"{year}-09-30"
            q3_data = self._query_quarter(db_conn, asset_id, q3_date)
            return self._subtract(cumulative_data, q3_data)
        
        else:
            # 非标准季度末，直接返回
            return cumulative_data
    
    def _query_quarter(self, db_conn: sqlite3.Connection, asset_id: str, 
                      report_date: str) -> Optional[Dict[str, Any]]:
        """查询指定季度的数据"""
        cursor = db_conn.cursor()
        cursor.execute("""
            SELECT revenue_ttm, net_profit_ttm, operating_cashflow
            FROM financial_history
            WHERE asset_id = ? AND report_date = ?
        """, (asset_id, report_date))
        
        row = cursor.fetchone()
        if not row:
            return None
        
        return {
            'revenue': row[0],
            'net_profit': row[1],
            'operating_cashflow': row[2]
        }
    
    def _subtract(self, cumul: Dict[str, Any], previous: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """
        仅对流量指标做减法
        
        Args:
            cumul: 累计值
            previous: 前期累计值
            
        Returns:
            Dict: 单季度值
        """
        result = {}
        
        for key, value in cumul.items():
            if key in self.FLOW_METRICS and value is not None:
                # 流量指标：做减法
                prev_val = previous.get(key, 0) if previous else 0
                result[key] = value - prev_val if prev_val is not None else value
            else:
                # 存量指标：保持原值
                result[key] = value
        
        return result
    
    def validate_quarterly_data(self, quarterly_data: Dict[str, Any]) -> bool:
        """
        验证单季度数据合理性
        
        Returns:
            bool: 数据是否合理
        """
        # 检查关键指标是否为负（除了特殊情况）
        if quarterly_data.get('revenue') and quarterly_data['revenue'] < 0:
            return False
        
        if quarterly_data.get('net_profit') and quarterly_data['net_profit'] < -1e10:
            # 允许适度亏损，但不能过大
            return False
        
        return True
