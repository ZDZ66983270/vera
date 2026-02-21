import yfinance as yf
import pandas as pd
import sqlite3
from datetime import datetime

DB_PATH = "vera.db"

def backfill_financials(symbol="TSLA", asset_id="US:STOCK:TSLA"):
    print(f"Fetching financials for {symbol}...")
    ticker = yf.Ticker(symbol)
    
    # 1. Fetch Income Statement (Annual & Quarterly)
    # We want TTM EPS.
    # yfinance 'financials' dataframe has columns as dates.
    
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # Fetch History (Annual)
    fin = ticker.financials
    if fin is not None and not fin.empty:
        print(f"Found {len(fin.columns)} annual reports.")
        _save_reports(cur, asset_id, fin, "Annual")
        
    # Fetch Quarterly
    q_fin = ticker.quarterly_financials
    if q_fin is not None and not q_fin.empty:
        print(f"Found {len(q_fin.columns)} quarterly reports.")
        _save_reports(cur, asset_id, q_fin, "Quarterly")
        
    conn.commit()
    conn.close()
    print("Backfill complete.")

def _save_reports(cur, asset_id, df, period_type):
    # transpose: Index = Date, Columns = Metric
    df_T = df.T 
    
    for date_idx, row in df_T.iterrows():
        # date_idx is Timestamp
        report_date = date_idx.strftime("%Y-%m-%d")
        
        # Extract metrics (Yahoo keys vary, try common ones)
        # 'Basic EPS', 'Diluted EPS', 'Net Income', 'Total Revenue'
        
        # EPS (Diluted is safer for TTM)
        eps = row.get("Diluted EPS") or row.get("Basic EPS")
        if pd.isna(eps): eps = None
        
        rev = row.get("Total Revenue") or row.get("Operating Revenue")
        if pd.isna(rev): rev = None
        
        net_inc = row.get("Net Income") or row.get("Net Income Common Stockholders")
        if pd.isna(net_inc): net_inc = None
        
        print(f"Saving {period_type} {report_date}: EPS={eps}, Revenue={(rev/1e9 if rev else 0):.2f}B")
        
        if eps is None: continue

        # Insert into financial_history
        # Assuming eps_ttm can be approximated by Annual EPS or 4*Quarterly (Rough)
        # Better: Store raw and let logic calc TTM. But our logic expects eps_ttm.
        # For Annual, EPS is TTM. 
        # For Quarterly, it is single quarter. We need to sum last 4.
        # Keep it simple: VERA v1 assumes report is annual or we use 'eps_ttm' field.
        # If we save strictly annual reports from `ticker.financials`, they ARE TTM for that year.
        # If we use quarterly, we need to roll.
        
        # Let's save Annual explicitly as TTM for now to get valid history points.
        if period_type == "Annual":
            cur.execute("""
                INSERT INTO financial_history (asset_id, report_date, eps_ttm, revenue_ttm, net_profit_ttm)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(asset_id, report_date) DO UPDATE SET
                    eps_ttm = excluded.eps_ttm,
                    revenue_ttm = excluded.revenue_ttm,
                    net_profit_ttm = excluded.net_profit_ttm
            """, (asset_id, report_date, float(eps), float(rev) if rev else None, float(net_inc) if net_inc else None))

        # TODO: Handle quarterly rolling TTM later. For now, 4 years of annual data gives 4 PE points.
        # Yahoo usually gives 4 years.
        
if __name__ == "__main__":
    backfill_financials()
