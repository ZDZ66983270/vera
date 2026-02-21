
import sqlite3
from db.connection import get_connection
from engine.asset_resolver import _infer_market, _infer_asset_type

def normalize_database():
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. Get all assets
    cursor.execute("SELECT asset_id, symbol_name FROM assets")
    assets = cursor.fetchall()
    
    print(f"Starting database normalization for {len(assets)} assets...")
    
    for old_id, name in assets:
        # Heuristic inference
        m = _infer_market(old_id)
        t = _infer_asset_type(old_id)
        t_map = {"EQUITY": "STOCK", "STOCK": "STOCK", "ETF": "ETF", "INDEX": "INDEX"}
        kind = t_map.get(t, "STOCK")
        
        # Standardize code
        code = old_id.upper()
        if ":" in code:
            code = code.split(":")[-1]
        
        # Remove suffixes for CN/HK
        for sfx in [".SS", ".SZ", ".SH", ".HK"]:
            code = code.replace(sfx, "")
            
        if m == "HK":
            code = code.zfill(5)
            
        new_id = f"{m}:{kind}:{code}"
        
        if old_id != new_id:
            print(f"  Migrating {old_id} -> {new_id}...")
            
            # Update all tables
            cursor.execute("UPDATE OR IGNORE assets SET asset_id = ? WHERE asset_id = ?", (new_id, old_id))
            cursor.execute("UPDATE OR IGNORE asset_universe SET asset_id = ? WHERE asset_id = ?", (new_id, old_id))
            cursor.execute("UPDATE OR IGNORE asset_symbol_map SET canonical_id = ? WHERE canonical_id = ?", (new_id, old_id))
            cursor.execute("UPDATE OR IGNORE asset_classification SET asset_id = ? WHERE asset_id = ?", (new_id, old_id))
            cursor.execute("UPDATE OR IGNORE quality_snapshot SET asset_id = ? WHERE asset_id = ?", (new_id, old_id))
            cursor.execute("UPDATE OR IGNORE vera_price_cache SET symbol = ? WHERE symbol = ?", (new_id, old_id))
            
            # If the current asset_id was also being used as a raw symbol in mapping, update that too if it's the provider symbol
            # (But usually provider symbols like 'TSLA' or '00700.HK' should stay as 'symbol' column)
            
            # Clean up old records if update ignored due to conflict
            cursor.execute("DELETE FROM assets WHERE asset_id = ?", (old_id,))
            cursor.execute("DELETE FROM asset_universe WHERE asset_id = ?", (old_id,))
            
        # 2. Ensure self-mapping exists in asset_symbol_map
        cursor.execute("""
            INSERT OR IGNORE INTO asset_symbol_map (canonical_id, symbol, source, priority, is_active)
            VALUES (?, ?, 'system', 10, 1)
        """, (new_id, new_id))

    conn.commit()
    print("\n✅ Database normalization complete.")
    conn.close()

if __name__ == "__main__":
    normalize_database()
