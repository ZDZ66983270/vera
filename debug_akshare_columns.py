import akshare as ak
import pandas as pd

def check_cn_columns(symbol="600036"):
    print(f"\n--- CN Bank ({symbol}) Columns ---")
    try:
        df = ak.stock_financial_report_sina(stock=symbol, symbol="利润表")
        print(f"Columns found: {len(df.columns)}")
        # Print columns that might be relevant
        targets = ["利息", "手续费", "佣金", "收入", "Revenue", "Interest", "Fee"]
        for col in df.columns:
            if any(t in str(col) for t in targets):
                print(f"  {col}")
                
        # Also check first row values for these
        if not df.empty:
            print("Sample Row 0:")
            for col in df.columns:
                if any(t in str(col) for t in targets):
                     print(f"    {col}: {df.iloc[0][col]}")
    except Exception as e:
        print(f"Error CN: {e}")

def check_hk_columns(symbol="03968"):
    print(f"\n--- HK Bank ({symbol}) Columns (Indicator) ---")
    try:
        # Check Indicator first (used in current script)
        df_ind = ak.stock_financial_hk_analysis_indicator_em(symbol=symbol, indicator="报告期")
        print(f"[Indicator] Columns found: {len(df_ind.columns)}")
        targets = ["利息", "手续费", "佣金", "收入", "Revenue", "Interest", "Fee", "NET_INTEREST", "FEE_INCOME"]
        for col in df_ind.columns:
            if any(t in str(col) for t in targets):
                print(f"  {col}")
                
        # Check detailed report if available?
        # ak.stock_financial_hk_report_em (EastMoney) or standard income statement?
        # Likely stock_financial_hk_report_em (Main Financial Report)
        print("\n--- HK Bank ({symbol}) Columns (Detail Report) ---")
        # Trying a likely function name or general report
        # ak.stock_financial_hk_report_em provides "ZCFZ", "LR", "XJLL" (Balance Sheet, Income, Cash Flow)
        # LR = Lirun (Income Statement)
        # Note: Function signature might be stock_financial_hk_report_em(symbol="03968", symbol="LR")?
        # Let's try finding the function in akshare docs or guessing common pattern
        # Common pattern: stock_financial_hk_report_em
    except Exception as e:
        print(f"Error HK Indicator: {e}")

def check_yf_columns(symbol="03968.HK"):
    import yfinance as yf
    print(f"\n--- Yahoo Finance ({symbol}) Columns ---")
    try:
        tk = yf.Ticker(symbol)
        fin = tk.financials
        print(f"Financials Shape: {fin.shape}")
        if not fin.empty:
            print("Rows (Indices):")
            # We want to see if specific rows exist
            targets = ["Interest", "Fee", "Non Interest", "Revenue"]
            for idx in fin.index:
                if any(t in str(idx) for t in targets):
                    print(f"  {idx}")
    except Exception as e:
        print(f"Error YF: {e}")

def explore_hk_akshare():
    print("\n--- Exploring AkShare HK Functions ---")
    try:
        # List all methods containing 'hk' and 'financial'
        methods = [m for m in dir(ak) if 'hk' in m and 'financial' in m]
        print(f"Found {len(methods)} methods:")
        for m in methods:
            print(f"  {m}")
            
        # Try stock_financial_hk_report_em (Income Statement) if found
        if 'stock_financial_hk_report_em' in methods:
             print("\nTrying stock_financial_hk_report_em (LR - Income)...")
             # symbol="00998" (09988? 03968?)
             try:
                 df = ak.stock_financial_hk_report_em(symbol="03968", indicator="利润表") # Guessing indicator name
                 print(f"Columns: {df.columns.tolist()[:10]}...")
                 if '净利息收入' in df.values or 'Net Interest Income' in str(df.columns):
                     print("Found potential interest income!")
             except Exception as e:
                 print(f"Failed '利润表': {e}")
                 
             try:
                 df = ak.stock_financial_hk_report_em(symbol="03968", indicator="业绩摘要")
                 print(f"Columns (Summary): {df.columns.tolist()[:5]}...")
             except: pass

    except Exception as e:
        print(f"Error Exploring: {e}")

if __name__ == "__main__":
    check_cn_columns()
    check_yf_columns("03968.HK") # CMBC
    # explore_hk_akshare()
