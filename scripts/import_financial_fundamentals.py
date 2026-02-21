
import pandas as pd
import sqlite3
import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db.connection import get_connection

CSV_PATH = "imports/financial_fundamentals.csv"

def import_financial_fundamentals():
    """
    Import financial fundamentals data from CSV to financial_fundamentals table.
    This table stores annual financial reports with full metrics.
    """
    if not os.path.exists(CSV_PATH):
        print(f"File not found: {CSV_PATH}")
        return

    print(f"Reading {CSV_PATH}...")
    df = pd.read_csv(CSV_PATH)
    
    conn = get_connection()
    cursor = conn.cursor()
    
    inserted = 0
    updated = 0
    skipped = 0
    errors = 0
    
    for _, row in df.iterrows():
        try:
            symbol = str(row['symbol']).strip()
            as_of_date = str(row['as_of_date']).strip()
            
            if not as_of_date or pd.isna(as_of_date):
                skipped += 1
                continue
            
            # Extract all fields
            revenue_ttm = row.get('revenue_ttm')
            net_income_ttm = row.get('net_income_ttm')
            operating_cashflow_ttm = row.get('operating_cashflow_ttm')
            free_cashflow_ttm = row.get('free_cashflow_ttm')
            total_assets = row.get('total_assets')
            total_liabilities = row.get('total_liabilities')
            total_debt = row.get('total_debt')
            cash_and_equivalents = row.get('cash_and_equivalents')
            net_debt = row.get('net_debt')
            debt_to_equity = row.get('debt_to_equity')
            interest_coverage = row.get('interest_coverage')
            current_ratio = row.get('current_ratio')
            dividend_yield = row.get('dividend_yield')
            payout_ratio = row.get('payout_ratio')
            buyback_ratio = row.get('buyback_ratio')
            data_source = row.get('data_source', 'csv-import')
            currency = row.get('currency', 'CNY')
            
            # Convert NaN to None
            def clean_value(val):
                return None if pd.isna(val) else float(val) if isinstance(val, (int, float)) else val
            
            revenue_ttm = clean_value(revenue_ttm)
            net_income_ttm = clean_value(net_income_ttm)
            operating_cashflow_ttm = clean_value(operating_cashflow_ttm)
            free_cashflow_ttm = clean_value(free_cashflow_ttm)
            total_assets = clean_value(total_assets)
            total_liabilities = clean_value(total_liabilities)
            total_debt = clean_value(total_debt)
            cash_and_equivalents = clean_value(cash_and_equivalents)
            net_debt = clean_value(net_debt)
            debt_to_equity = clean_value(debt_to_equity)
            interest_coverage = clean_value(interest_coverage)
            current_ratio = clean_value(current_ratio)
            dividend_yield = clean_value(dividend_yield)
            payout_ratio = clean_value(payout_ratio)
            buyback_ratio = clean_value(buyback_ratio)
            
            # Check if record exists
            cursor.execute("""
                SELECT 1 FROM financial_fundamentals 
                WHERE asset_id = ? AND as_of_date = ?
            """, (symbol, as_of_date))
            
            exists = cursor.fetchone()
            
            if exists:
                # Update
                cursor.execute("""
                    UPDATE financial_fundamentals
                    SET revenue_ttm = ?, net_income_ttm = ?, operating_cashflow_ttm = ?,
                        free_cashflow_ttm = ?, total_assets = ?, total_liabilities = ?,
                        total_debt = ?, cash_and_equivalents = ?, net_debt = ?,
                        debt_to_equity = ?, interest_coverage = ?, current_ratio = ?,
                        dividend_yield = ?, payout_ratio = ?, buyback_ratio = ?,
                        data_source = ?, currency = ?
                    WHERE asset_id = ? AND as_of_date = ?
                """, (revenue_ttm, net_income_ttm, operating_cashflow_ttm,
                      free_cashflow_ttm, total_assets, total_liabilities,
                      total_debt, cash_and_equivalents, net_debt,
                      debt_to_equity, interest_coverage, current_ratio,
                      dividend_yield, payout_ratio, buyback_ratio,
                      data_source, currency, symbol, as_of_date))
                updated += 1
            else:
                # Insert
                cursor.execute("""
                    INSERT INTO financial_fundamentals (
                        asset_id, as_of_date, revenue_ttm, net_income_ttm, operating_cashflow_ttm,
                        free_cashflow_ttm, total_assets, total_liabilities, total_debt,
                        cash_and_equivalents, net_debt, debt_to_equity, interest_coverage,
                        current_ratio, dividend_yield, payout_ratio, buyback_ratio,
                        data_source, currency
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (symbol, as_of_date, revenue_ttm, net_income_ttm, operating_cashflow_ttm,
                      free_cashflow_ttm, total_assets, total_liabilities, total_debt,
                      cash_and_equivalents, net_debt, debt_to_equity, interest_coverage,
                      current_ratio, dividend_yield, payout_ratio, buyback_ratio,
                      data_source, currency))
                inserted += 1
                
        except Exception as e:
            print(f"Error processing row {row.get('symbol')}: {e}")
            errors += 1
    
    conn.commit()
    conn.close()
    
    print(f"\nImport Complete:")
    print(f"  Inserted: {inserted}")
    print(f"  Updated: {updated}")
    print(f"  Skipped: {skipped}")
    print(f"  Errors: {errors}")

if __name__ == "__main__":
    import_financial_fundamentals()
