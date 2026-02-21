
import akshare as ak
import pandas as pd

symbol = "600030"
try:
    df_fin = ak.stock_financial_report_sina(stock=symbol, symbol="利润表")
    print("Columns:", df_fin.columns)
    print("First 5 rows EPS:")
    print(df_fin[["报表日期", "基本每股收益", "净利润"]].head())
    
    # Check types
    for i, row in df_fin.head().iterrows():
        val = row.get("基本每股收益")
        print(f"Row {i} EPS: '{val}' type: {type(val)}")
        try:
            f = float(val)
            print(f"  -> float: {f}")
        except Exception as e:
            print(f"  -> error: {e}")
            
except Exception as e:
    print(e)
