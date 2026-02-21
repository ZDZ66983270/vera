import pandas as pd
import sqlite3
import re

CSV_PATH = "imports/market_data_daily_full.csv"
DB_PATH = "vera.db"

def classify_cn_symbol(raw_sym):
    """
    Heuristic rule for CN symbols (.SS, .SZ)
    Returns canonical_id or None if unsure
    """
    raw_sym = raw_sym.upper()
    if not (raw_sym.endswith(".SS") or raw_sym.endswith(".SZ") or raw_sym.endswith(".SH")):
        return None
        
    code = raw_sym.split(".")[0]
    suffix = raw_sym.split(".")[1]
    
    # Rules
    # Shanghai Index: 000xxx
    if (suffix == "SS" or suffix == "SH") and code.startswith("000"):
        return f"CN:INDEX:{code}"
        
    # Shenzhen Index: 399xxx.SZ
    if suffix == "SZ" and code.startswith("399"):
        return f"CN:INDEX:{code}"
        
    # SH Stocks
    if suffix == "SS" or suffix == "SH":
        # 000xxx handled above (Index)
        return f"CN:STOCK:{code}"
        
    if suffix == "SZ":
        # 399xxx handled above (Index)
        return f"CN:STOCK:{code}"
        
    return None

def analyze():
    print(f"Reading {CSV_PATH}...")
    df = pd.read_csv(CSV_PATH)
    # Find symbol col
    sym_col = next((c for c in df.columns if 'symbol' in c.lower()), None)
    if not sym_col:
        print("No symbol column found.")
        return
        
    raw_symbols = df[sym_col].dropna().unique()
    print(f"Found {len(raw_symbols)} unique symbols.")
    
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    to_insert = []
    
    for rs in raw_symbols:
        rs = str(rs).strip().upper()
        # Check if already mapped
        cur.execute("SELECT canonical_id FROM asset_symbol_map WHERE symbol = ?", (rs,))
        if cur.fetchone():
            continue # Already mapped
            
        # Try classify
        canon = classify_cn_symbol(rs)
        if canon:
            print(f"New Map: {rs} -> {canon}")
            to_insert.append((canon, rs, 'csv_auto_safe'))
        elif re.match(r'^\d{6}\.(SS|SZ)$', rs):
            print(f"[WARN] Unclassified CN symbol: {rs}")
            
    if to_insert:
        print(f"Registering {len(to_insert)} new mappings...")
        cur.executemany(
            "INSERT OR IGNORE INTO asset_symbol_map (canonical_id, symbol, source) VALUES (?, ?, ?)",
            to_insert
        )
        conn.commit()
        print("Done.")
    else:
        print("No new mappings needed.")
        
    conn.close()

if __name__ == "__main__":
    analyze()
