import sqlite3
import json
from analysis.quality_assessment import build_quality_flags

DB_PATH = "data/stock_analyzer.db"

def get_connection():
    return sqlite3.connect(DB_PATH)

def fetch_fundamentals(asset_id: str, conn):
    cursor = conn.cursor()
    
    # 1. Fetch TTM data
    cursor.execute("""
        SELECT * FROM financial_fundamentals 
        WHERE asset_id = ? 
        ORDER BY as_of_date DESC LIMIT 1
    """, (asset_id,))
    ttm_row = cursor.fetchone()
    ttm_cols = [description[0] for description in cursor.description] if ttm_row else []
    ttm_data = dict(zip(ttm_cols, ttm_row)) if ttm_row else {}
    
    # 2. Fetch History
    cursor.execute("""
        SELECT * FROM fundamentals_annual 
        WHERE asset_id = ? 
        ORDER BY fiscal_year ASC
    """, (asset_id,))
    hist_rows = cursor.fetchall()
    hist_cols = [description[0] for description in cursor.description] if hist_rows else []
    
    revenue_history = []
    shares_history = []
    
    for r in hist_rows:
        row_dict = dict(zip(hist_cols, r))
        revenue_history.append(row_dict.get('total_revenue'))
        shares_history.append(row_dict.get('shares_outstanding'))
        
    # 3. Fetch Sector
    # Try querying assets table first (created by me)
    # If not found there, handle gracefully.
    try:
        cursor.execute("SELECT sector FROM assets WHERE asset_id = ?", (asset_id,))
        res = cursor.fetchone()
        sector = res[0] if res else None
    except:
        sector = None
    
    combined = ttm_data.copy()
    combined['revenue_history'] = revenue_history
    # Calculate shares YoY if history exists
    if len(shares_history) >= 2:
        try:
            current = float(shares_history[-1])
            prev = float(shares_history[-2])
            if prev > 0:
                combined['shares_out_yoy_growth'] = (current / prev) - 1.0
        except:
            pass
            
    combined['sector'] = sector
    return combined

def main():
    target_symbol = "TSLA"
    conn = get_connection()
    
    print(f"--- Fetching Data for {target_symbol} ---")
    data = fetch_fundamentals(target_symbol, conn)
    conn.close()
    
    if not data:
        print("No data found!")
        return

    print(f"\n--- Raw Input Data (Fetched from DB) ---")
    for k, v in data.items():
        if k == 'revenue_history':
            print(f"{k}: {v} (Len: {len(v) if v else 0})")
        else:
            print(f"{k}: {v}")
            
    print("\n--- Running Quality Assessment ---")
    result = build_quality_flags(data)
    
    print(f"\nQuality Buffer Level: {result['quality_buffer_level']}")
    print(f"Summary: {result['quality_summary']}")
    
    print("\n--- 9 Flags Details ---")
    
    flags_list = [
        "revenue_stability_flag",
        "cyclicality_flag",
        "moat_proxy_flag",
        "balance_sheet_flag",
        "cashflow_coverage_flag",
        "leverage_risk_flag",
        "payout_consistency_flag",
        "dilution_risk_flag",
        "regulatory_dependence_flag"
    ]
    
    # Extract notes from the flat list if possible, or just print the flags
    # build_quality_flags returns a dict with keys for flags and 'quality_notes' list
    
    # Let's match notes to flags for display
    notes = result.get('quality_notes', [])
    notes_map = {}
    for n in notes:
        if ": " in n:
            key, val = n.split(": ", 1)
            if key not in notes_map:
                notes_map[key] = []
            notes_map[key].append(val)
            
    for f in flags_list:
        val = result.get(f, "N/A")
        print(f"{f:<25} : {val:<10} | {', '.join(notes_map.get(f, []))}")

if __name__ == "__main__":
    main()
