import sqlite3
import yfinance as yf
import time
import re
import sys
import os

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from db.connection import get_connection

def get_etfs_missing_data(conn):
    """
    Fetch ETFs from asset_universe that are missing sector_proxy_id (benchmark_etf), 
    market_index_id (benchmark_index), or classification data.
    """
    cursor = conn.cursor()
    query = """
        SELECT u.asset_id, u.primary_symbol, a.name 
        FROM asset_universe u 
        JOIN assets a ON u.asset_id = a.asset_id 
        WHERE a.asset_type = 'ETF' 
        AND (u.sector_proxy_id IS NULL OR u.market_index_id IS NULL 
             OR NOT EXISTS (SELECT 1 FROM asset_classification ac WHERE ac.asset_id = u.asset_id))
    """
    cursor.execute(query)
    return cursor.fetchall()

def fetch_us_etf_info(symbol):
    """
    Fetch ETF metadata from yfinance for US ETFs.
    """
    try:
        # Handle cases where symbol might need adjustment for yfinance (usually OK for US)
        t = yf.Ticker(symbol)
        info = t.info
        return {
            'category': info.get('category'),
            'semmary': info.get('longBusinessSummary', '')
        }
    except Exception as e:
        print(f"Error fetching {symbol}: {e}")
        return None

def infer_classification_from_us_data(info):
    """
    Map yfinance category/summary to Sector, Industry, Benchmark.
    """
    category = info.get('category', '')
    summary = info.get('summary', '')
    
    # Heuristic Mapping (English Targets)
    mapping = {
        'Technology': ('Information Technology', 'Technology', 'US:ETF:XLK', None),
        'Financial': ('Financials', 'Financials', 'US:ETF:XLF', None),
        'Health': ('Health Care', 'Health Care', 'US:ETF:XLV', None),
        'Energy': ('Energy', 'Energy', 'US:ETF:XLE', None),
        'Real Estate': ('Real Estate', 'Real Estate', 'US:ETF:XLRE', None),
        'Consumer Cyclical': ('Consumer Discretionary', 'Consumer', 'US:ETF:XLY', None),
        'Consumer Defensive': ('Consumer Staples', 'Consumer', 'US:ETF:XLP', None),
        'Utilities': ('Utilities', 'Utilities', 'US:ETF:XLU', None),
        'Industrials': ('Industrials', 'Industrials', 'US:ETF:XLI', None),
        'Materials': ('Materials', 'Materials', 'US:ETF:XLB', None),
        'Communications': ('Communication Services', 'Communication Services', 'US:ETF:XLC', None),
        'Precious Metals': ('Materials', 'Precious Metals', 'US:ETF:GLD', None),
        'Large Blend': ('Integrated', 'Broad Market', 'US:ETF:SPY', 'US:INDEX:^GSPC'),
        'Large Value': ('Integrated', 'Broad Market', 'US:ETF:VTV', None),
        'Large Growth': ('Integrated', 'Broad Market', 'US:ETF:VUG', None),
        'Small Blend': ('Integrated', 'Small Cap', 'US:ETF:IWM', 'US:INDEX:^RUT'),
    }
    
    for key, val in mapping.items():
        if category and key in category:
            return val
            
    # Fallback to Summary keywords if category is vague or missing
    summary_lower = summary.lower()
    if 'semiconductor' in summary_lower:
        return ('Information Technology', 'Semiconductors', 'US:ETF:SOXX', None)
    if 'gold' in summary_lower:
        return ('Materials', 'Precious Metals', 'US:ETF:GLD', None)
    if 'bitcoin' in summary_lower:
        return ('Alternative', 'Crypto Asset', 'WORLD:CRYPTO:BTC-USD', None)
        
    return None, None, None, None

def infer_cn_hk_classification(name):
    """
    Infer classification from CN/HK ETF names using keywords.
    """
    # Heuristic Mapping (English Targets)
    name_map = {
        '科技': ('Information Technology', 'Technology', 'HK:ETF:03033', 'HK:INDEX:HSTECH'),
        '半导体': ('Information Technology', 'Semiconductors', None, None),
        '芯片': ('Information Technology', 'Semiconductors', None, None),
        '软件': ('Information Technology', 'Software', None, None),
        '金融': ('Financials', 'Financials', None, None),
        '银行': ('Financials', 'Banks', None, None),
        '券商': ('Financials', 'Capital Markets', None, None),
        '证券': ('Financials', 'Capital Markets', None, None),
        '医药': ('Health Care', 'Health Care', None, None),
        '医疗': ('Health Care', 'Health Care', None, None),
        '能源': ('Energy', 'Energy', None, None),
        '消费': ('Consumer Discretionary', 'Consumer', None, None),
        '红利': ('Integrated', 'High Dividend', 'US:ETF:VYM', None),
        '高股息': ('Integrated', 'High Dividend', 'HK:ETF:03110', None),
        '恒生科技': ('Information Technology', 'Technology', 'HK:ETF:03033', 'HK:INDEX:HSTECH'),
        '沪深300': ('Integrated', 'Broad Market', 'CN:ETF:510300', 'CN:INDEX:000300'),
        '科创50': ('Information Technology', 'Technology', 'CN:ETF:588000', 'CN:INDEX:000688'),
        '恒生指数': ('Integrated', 'Broad Market', 'HK:ETF:02800', 'HK:INDEX:HSI'),
        '纳指': ('Integrated', 'Broad Market', 'US:ETF:QQQ', 'US:INDEX:^NDX'),
        '标普': ('Integrated', 'Broad Market', 'US:ETF:SPY', 'US:INDEX:^GSPC'),
        '黄金': ('Materials', 'Precious Metals', 'US:ETF:GLD', None),
    }
    
    for key, val in name_map.items():
        if key in name:
            return val
            
    return None, None, None, None

def update_db(conn, asset_id, sector, industry, bench_etf, bench_idx):
    """
    Update database with classification and benchmarks.
    """
    cursor = conn.cursor()
    from datetime import datetime
    now_date = datetime.now().strftime("%Y-%m-%d")
    
    # 1. Update Asset Universe (Benchmarks)
    if bench_etf or bench_idx:
        cursor.execute("""
            UPDATE asset_universe 
            SET sector_proxy_id = COALESCE(?, sector_proxy_id),
                market_index_id = COALESCE(?, market_index_id)
            WHERE asset_id = ?
        """, (bench_etf, bench_idx, asset_id))
    
    # 2. Update Asset Classification (Sector/Industry)
    if sector or industry:
        # Check if classification exists
        cursor.execute("SELECT 1 FROM asset_classification WHERE asset_id = ? AND scheme = 'GICS'", (asset_id,))
        exists = cursor.fetchone()
        
        if exists:
            cursor.execute("""
                UPDATE asset_classification 
                SET sector_name = COALESCE(?, sector_name),
                    industry_name = COALESCE(?, industry_name),
                    as_of_date = ?
                WHERE asset_id = ? AND scheme = 'GICS'
            """, (sector, industry, now_date, asset_id))
        else:
            cursor.execute("""
                INSERT INTO asset_classification (asset_id, scheme, sector_name, industry_name, as_of_date, is_active)
                VALUES (?, 'GICS', ?, ?, ?, 1)
            """, (asset_id, sector, industry, now_date))
    
    conn.commit()

def main():
    conn = get_connection()
    etfs = get_etfs_missing_data(conn)
    print(f"Found {len(etfs)} ETFs with missing data.")
    
    for asset_id, primary_symbol, name in etfs:
        print(f"Processing {primary_symbol} ({name})...")
        
        sector = None
        industry = None
        bench_etf = None
        bench_idx = None
        
        # Strategy 1: US Heuristic via yfinance
        if asset_id.startswith("US:"):
            # Extract clean ticker for yfinance (remove US:ETF: prefix)
            ticker = primary_symbol if ":" not in primary_symbol else primary_symbol.split(":")[-1]
            info = fetch_us_etf_info(ticker)
            if info:
                sector, industry, bench_etf, bench_idx = infer_classification_from_us_data(info)
                if sector:
                    print(f"  [US-Web] Mapped to {sector} / {industry}")
        
        # Strategy 2: CN/HK/Fallback Heuristic via Name
        if not sector: # If US fetch failed or not US
            sector, industry, bench_etf_kw, bench_idx_kw = infer_cn_hk_classification(name)
            if sector:
                print(f"  [Name-Rule] Mapped to {sector} / {industry}")
                if bench_etf_kw: bench_etf = bench_etf_kw
                if bench_idx_kw: bench_idx = bench_idx_kw
        
        if sector or bench_etf:
            update_db(conn, asset_id, sector, industry, bench_etf, bench_idx)
            print(f"  -> Updated DB.")
        else:
            print("  -> Could not classify.")
            
        time.sleep(0.5) # Be polite to API
        
    conn.close()
    print("Done.")

if __name__ == "__main__":
    main()
