
import pandas as pd
import sqlite3
import os
import sys

import sys
sys.path.append(os.getcwd())
from db.connection import get_connection

# DB_PATH removed, using db.connection default
CSV_PATH = 'imports/financials_overview_v2.csv'



def recreate_tables(conn):
    print("Recreating tables...")
    cur = conn.cursor()
    
    # fundamentals_annual
    cur.execute("DROP TABLE IF EXISTS fundamentals_annual")
    cur.execute("""
        CREATE TABLE fundamentals_annual (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_id TEXT NOT NULL,
            fiscal_year INTEGER NOT NULL,
            total_revenue REAL,
            net_income REAL,
            total_assets REAL,
            total_liabilities REAL,
            total_debt REAL,
            cash_and_equivalents REAL,
            operating_cashflow REAL,
            shares_outstanding REAL, 
            eps_diluted REAL,
            UNIQUE(asset_id, fiscal_year)
        )
    """)

    # financial_fundamentals
    cur.execute("DROP TABLE IF EXISTS financial_fundamentals")
    cur.execute("""
        CREATE TABLE financial_fundamentals (
            asset_id TEXT PRIMARY KEY,
            as_of_date TEXT, -- YYYY-MM-DD
            revenue_ttm REAL,
            net_income_ttm REAL,
            operating_cashflow_ttm REAL,
            free_cashflow_ttm REAL,
            total_assets REAL,
            total_liabilities REAL,
            total_debt REAL,
            cash_and_equivalents REAL,
            net_debt REAL, -- Derived or stored
            debt_to_equity REAL,
            interest_coverage REAL,
            current_ratio REAL,
            dividend_yield REAL,
            payout_ratio REAL,
            buyback_ratio REAL,
            data_source TEXT,
            currency TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # assets (for sector info)
    cur.execute("DROP TABLE IF EXISTS assets")
    cur.execute("CREATE TABLE IF NOT EXISTS assets (asset_id TEXT PRIMARY KEY, symbol TEXT, name TEXT, region TEXT, sector TEXT, industry TEXT, market TEXT, asset_type TEXT, index_role TEXT)")
    
    # quality_snapshot (ensure exists for update script later)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS quality_snapshot (
            snapshot_id TEXT PRIMARY KEY,
            asset_id TEXT,
            revenue_stability_flag TEXT,
            cyclicality_flag TEXT,
            moat_proxy_flag TEXT,
            balance_sheet_flag TEXT,
            cashflow_coverage_flag TEXT,
            leverage_risk_flag TEXT,
            payout_consistency_flag TEXT,
            dilution_risk_flag TEXT,
            regulatory_dependence_flag TEXT,
            quality_buffer_level TEXT,
            quality_summary TEXT,
            quality_notes TEXT,
            FOREIGN KEY(asset_id) REFERENCES assets(id)
        )
    """)
    
    # analysis_snapshot (dependency)
    cur.execute("DROP TABLE IF EXISTS analysis_snapshot")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS analysis_snapshot (
            snapshot_id TEXT PRIMARY KEY,
            asset_id TEXT,
            as_of_date TEXT,
            risk_level TEXT,
            valuation_status TEXT,
            quality_score REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()

def import_assets(conn):
    ASSETS_CSV = 'imports/asset_classification.csv'
    if not os.path.exists(ASSETS_CSV):
        print(f"Warning: {ASSETS_CSV} not found. Sector info might be missing.")
        return

    print(f"Importing Assets from {ASSETS_CSV}...")
    try:
        df = pd.read_csv(ASSETS_CSV)
        # Assume columns: symbol, name, sector, industry...
        cur = conn.cursor()
        for _, row in df.iterrows():
            # Minimal mapping
            aid = row.get('asset_id')
            if not aid: continue
            sector = row.get('sector_name', 'Unknown')
            industry = row.get('industry_name', 'Unknown')
            # Parse market/type from ID (e.g. HK:STOCK:00700)
            parts = aid.split(':')
            market = parts[0] if len(parts) > 0 else 'Unknown'
            atype = parts[1] if len(parts) > 1 else 'Unknown'
            company_name = row.get('name', aid)
            
            cur.execute("INSERT OR REPLACE INTO assets (asset_id, symbol, name, sector, industry, market, asset_type) VALUES (?, ?, ?, ?, ?, ?, ?)", 
                        (aid, aid, company_name, sector, industry, market, atype))
        conn.commit()
    except Exception as e:
        print(f"Error importing assets: {e}")

def import_csv_data():
    if not os.path.exists(CSV_PATH):
        print(f"Error: {CSV_PATH} not found.")
        return

    print(f"Reading {CSV_PATH}...")
    df = pd.read_csv(CSV_PATH)
    df.columns = [c.strip() for c in df.columns]
    
    conn = get_connection()
    try:
        recreate_tables(conn)
        import_assets(conn) # Import assets first
        
        cur = conn.cursor()
        records_count = 0
        
        for _, row in df.iterrows():
            symbol = row['symbol']
            date_str = str(row['as_of_date'])
            try:
                year = int(date_str.split('-')[0])
            except:
                continue
                
            # Parse values
            def get_val(col_name):
                val = row.get(col_name)
                if pd.isna(val) or val == '':
                    return None
                try:
                    return float(val)
                except:
                    return None

            # Multiplier for 亿 (10^8)
            UNIT_MULTIPLIER = 100000000.0

            revenue = get_val('revenue (亿)')
            net_in = get_val('net_income (亿)')
            assets = get_val('total_assets (亿)')
            liabilities = get_val('total_liabilities (亿)')
            debt = get_val('total_debt (亿)')
            cash = get_val('cash_and_equivalents (亿)')
            ocf = get_val('operating_cashflow (亿)')
            
            # Apply multiplier
            if revenue is not None: revenue *= UNIT_MULTIPLIER
            if net_in is not None: net_in *= UNIT_MULTIPLIER
            if assets is not None: assets *= UNIT_MULTIPLIER
            if liabilities is not None: liabilities *= UNIT_MULTIPLIER
            if debt is not None: debt *= UNIT_MULTIPLIER
            if cash is not None: cash *= UNIT_MULTIPLIER
            if ocf is not None: ocf *= UNIT_MULTIPLIER

            cur.execute("""
                INSERT OR REPLACE INTO fundamentals_annual (
                    asset_id, fiscal_year, total_revenue, net_income, 
                    total_assets, total_liabilities, total_debt, cash_and_equivalents, operating_cashflow
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (symbol, year, revenue, net_in, assets, liabilities, debt, cash, ocf))
            
            records_count += 1
        
        print("Syncing financial_fundamentals with latest annual data...")
        cur.execute("""
            INSERT OR REPLACE INTO financial_fundamentals (
                asset_id, as_of_date, revenue_ttm, net_income_ttm,
                total_assets, total_liabilities, total_debt, cash_and_equivalents,
                operating_cashflow_ttm,
                net_debt,
                debt_to_equity,
                created_at
            )
            SELECT 
                asset_id, 
                MAX(fiscal_year) || '-12-31', 
                total_revenue, 
                net_income,
                total_assets, 
                total_liabilities, 
                total_debt, 
                cash_and_equivalents,
                operating_cashflow,
                (total_debt - cash_and_equivalents),
                CASE WHEN (total_assets - total_liabilities) != 0 THEN total_debt / (total_assets - total_liabilities) ELSE NULL END,
                CURRENT_TIMESTAMP
            FROM fundamentals_annual
            GROUP BY asset_id
            HAVING fiscal_year = MAX(fiscal_year)
        """)
        
        conn.commit()
        print(f"Successfully imported {records_count} annual records and updated TTM table.")
        
    except Exception as e:
        print(f"Error during import: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    import_csv_data()
