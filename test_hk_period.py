
import akshare as ak
import pandas as pd

try:
    print("Fetching HK Financials for 01919 (Report Period)...")
    df = ak.stock_financial_hk_analysis_indicator_em(symbol="01919", indicator="报告期")
    print("Columns:", df.columns)
    
    # Check date and EPS_TTM
    # We want to see 2025 dates
    cols = ['REPORT_DATE', 'BASIC_EPS', 'EPS_TTM']
    # Filter for columns that actually exist
    valid_cols = [c for c in cols if c in df.columns]
    
    print(df[valid_cols].head(10))
    
except Exception as e:
    print(e)
