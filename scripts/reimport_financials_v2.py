
import csv
import sqlite3
import pandas as pd
from db.connection import get_connection
from utils.canonical_resolver import resolve_canonical_symbol

def import_financials_v2(csv_path="imports/financials_overview.csv"):
    print(f"Reading {csv_path}...")
    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        print(f"Failed to read CSV: {e}")
        return

    conn = get_connection()
    cursor = conn.cursor()
    
    # Pre-fetch existing assets for validation
    existing_assets = set(row[0] for row in cursor.execute("SELECT asset_id FROM assets").fetchall())
    
    successful_count = 0
    
    def parse_billion(val):
        try:
            if pd.isna(val) or val == "":
                return None
            return float(val) * 1e8
        except:
            return None

    def parse_float(val):
        try:
            if pd.isna(val) or val == "":
                return None
            return float(val)
        except:
            return None

    for _, row in df.iterrows():
        raw_symbol = str(row.get("symbol", "")).strip()
        as_of_date = str(row.get("as_of_date", "")).strip()
        
        if not raw_symbol or not as_of_date:
            continue
            
        # 1. Resolve Asset ID
        asset_id = None
        
        # Try brute force mapping for known patterns
        if raw_symbol in existing_assets:
            asset_id = raw_symbol
        else:
             # Heuristic: 600030.SH -> CN:STOCK:600030
             if raw_symbol.endswith(".SH") or raw_symbol.endswith(".SS"):
                 code = raw_symbol.split(".")[0]
                 candidate = f"CN:STOCK:{code}"
                 if candidate in existing_assets:
                     asset_id = candidate
             elif raw_symbol.endswith(".SZ"):
                 code = raw_symbol.split(".")[0]
                 candidate = f"CN:STOCK:{code}"
                 if candidate in existing_assets:
                     asset_id = candidate
             
             # Fallback to resolver if heuristic failed
             if not asset_id:
                 try:
                     asset_id = resolve_canonical_symbol(conn, raw_symbol, strict_ambiguous=False)
                 except:
                     pass
        
        if not asset_id or asset_id not in existing_assets:
            print(f"Skipping unknown asset: {raw_symbol} (Resolved: {asset_id})")
            continue

        # 2. Parse Metrics
        # Headers: total_debt (亿),cash_and_equivalents (亿),revenue (亿),net_income (亿),total_assets (亿),total_liabilities (亿),debt_to_equity,dividend_yield
        total_debt = parse_billion(row.get("total_debt (亿)"))
        cash = parse_billion(row.get("cash_and_equivalents (亿)"))
        revenue = parse_billion(row.get("revenue (亿)"))
        net_income = parse_billion(row.get("net_income (亿)"))
        assets = parse_billion(row.get("total_assets (亿)"))
        liabilities = parse_billion(row.get("total_liabilities (亿)"))
        
        d2e = parse_float(row.get("debt_to_equity"))
        dy = parse_float(row.get("dividend_yield"))
        currency = row.get("currency", "CNY")

        # 3. Upsert into financial_fundamentals (Using REPLACE to overwrite same date records)
        # Note: revenue -> revenue_ttm, net_income -> net_income_ttm (Assuming annual snapshots used as proxy)
        cursor.execute("""
            INSERT OR REPLACE INTO financial_fundamentals (
                asset_id, as_of_date, currency,
                revenue_ttm, net_income_ttm,
                total_assets, total_liabilities, total_debt, cash_and_equivalents,
                debt_to_equity, dividend_yield,
                data_source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'csv_import_v2')
        """, (
            asset_id, as_of_date, currency,
            revenue, net_income,
            assets, liabilities, total_debt, cash,
            d2e, dy
        ))
        
        successful_count += 1

    conn.commit()
    conn.close()
    print(f"Import complete. Successfully imported {successful_count} records.")

if __name__ == "__main__":
    import_financials_v2()
