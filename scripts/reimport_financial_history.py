
import pandas as pd
import sqlite3
import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.connection import get_connection
from utils.canonical_resolver import resolve_canonical_symbol

CSV_PATH = "imports/financial_history.csv"

def smart_resolve(conn, raw_symbol: str) -> str:
    """
    Enhanced resolution for known formats in the CSV
    """
    s = str(raw_symbol).strip().upper()
    
    # Already canonical
    if ":" in s:
        return s
        
    # HK Stocks (e.g. 00005.HK or 00700.HK)
    if s.endswith(".HK"):
        code = s.replace(".HK", "").zfill(5)
        return resolve_canonical_symbol(conn, code, market_hint="HK", asset_type_hint="STOCK")
        
    # CN Stocks (6 digits)
    if s.isdigit() and len(s) == 6:
        return resolve_canonical_symbol(conn, s, market_hint="CN", asset_type_hint="STOCK")
        
    # Fallback to standard resolver
    return resolve_canonical_symbol(conn, s)

def reimport_financial_history():
    if not os.path.exists(CSV_PATH):
        print(f"File not found: {CSV_PATH}")
        return

    print(f"Reading {CSV_PATH}...")
    df = pd.read_csv(CSV_PATH)
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # Clear table before re-import to ensure no duplicates/stale data
    print("Clearing existing financial_history data...")
    cursor.execute("DELETE FROM financial_history")
    
    history_inserted = 0
    skipped = 0
    errors = 0
    
    for _, row in df.iterrows():
        try:
            raw_symbol = str(row['symbol']).strip()
            as_of_date = str(row['as_of_date']).strip()
            
            if not as_of_date or pd.isna(as_of_date) or as_of_date == 'nan':
                skipped += 1
                continue
                
            # Resolve canonical ID
            asset_id = smart_resolve(conn, raw_symbol)
            
            # Unit conversion: 10^8 (亿 -> raw)
            # The CSV values like 673.96 are in '亿' (100 millions)
            def scale_it(val):
                if pd.isna(val) or val == '': return None
                try:
                    return float(val) * 100_000_000
                except:
                    return None

            # Populate financial_history (unified financial data table)
            revenue_ttm_raw = scale_it(row.get('revenue_ttm'))
            net_profit_ttm_raw = scale_it(row.get('net_income_ttm'))
            currency = str(row.get('currency')).strip() if not pd.isna(row.get('currency')) else 'CNY'
            
            cursor.execute("""
                INSERT INTO financial_history (
                    asset_id, report_date, revenue_ttm, net_profit_ttm, 
                    operating_cashflow_ttm, free_cashflow_ttm, total_assets, 
                    total_liabilities, total_debt, cash_and_equivalents, net_debt,
                    debt_to_equity, interest_coverage, current_ratio, 
                    dividend_yield, payout_ratio, buyback_ratio, currency
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                asset_id, as_of_date, 
                revenue_ttm_raw, 
                net_profit_ttm_raw,
                scale_it(row.get('operating_cashflow_ttm')),
                scale_it(row.get('free_cashflow_ttm')),
                scale_it(row.get('total_assets')),
                scale_it(row.get('total_liabilities')),
                scale_it(row.get('total_debt')),
                scale_it(row.get('cash_and_equivalents')),
                scale_it(row.get('net_debt')),
                row.get('debt_to_equity') if not pd.isna(row.get('debt_to_equity')) else None,
                row.get('interest_coverage') if not pd.isna(row.get('interest_coverage')) else None,
                row.get('current_ratio') if not pd.isna(row.get('current_ratio')) else None,
                row.get('dividend_yield') if not pd.isna(row.get('dividend_yield')) else None,
                row.get('payout_ratio') if not pd.isna(row.get('payout_ratio')) else None,
                row.get('buyback_ratio') if not pd.isna(row.get('buyback_ratio')) else None,
                currency
            ))
            history_inserted += 1
                
        except Exception as e:
            print(f"Error processing row {row.get('symbol')} on {row.get('as_of_date')}: {e}")
            errors += 1
            
    conn.commit()
    conn.close()
    print(f"\nImport Finished!")
    print(f"  Financial History records: {history_inserted}")
    print(f"  Skipped: {skipped}")
    print(f"  Errors: {errors}")

if __name__ == "__main__":
    reimport_financial_history()
