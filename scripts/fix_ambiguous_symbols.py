import sqlite3
from db.connection import get_connection

def fix_ambiguous_indices():
    """
    Inserts default mappings for common ambiguous CN symbols:
    000300 -> CN:INDEX:000300 (CSI 300)
    000300.SS -> CN:INDEX:000300
    000001 -> CN:INDEX:000001 (SSE Composite)
    000001.SS -> CN:INDEX:000001
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    print("Applying Ambiguity Fixes...")
    
    mappings = [
        # raw_symbol, canonical_id, note
        ("000300", "CN:INDEX:000300", "Default to CSI 300 Index"),
        ("000300.SS", "CN:INDEX:000300", "CSI 300 Index (SS)"),
        ("000001", "CN:INDEX:000001", "Default to SSE Composite"),
        ("000001.SS", "CN:INDEX:000001", "SSE Composite"),
        ("000905", "CN:INDEX:000905", "CSI 500"),
        ("000905.SS", "CN:INDEX:000905", "CSI 500 (SS)"),
        ("000852", "CN:INDEX:000852", "CSI 1000"),
        ("000852.SS", "CN:INDEX:000852", "CSI 1000 (SS)"),
        ("399001", "CN:INDEX:399001", "SZSE Component"),
        ("399001.SZ", "CN:INDEX:399001", "SZSE Component"),
        ("399006", "CN:INDEX:399006", "ChiNext"),
        ("399006.SZ", "CN:INDEX:399006", "ChiNext"),
    ]
    
    cnt = 0
    for raw, canonical, note in mappings:
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO asset_symbol_map (symbol, canonical_id, note, is_active, priority)
                VALUES (?, ?, ?, 1, 100)
            """, (raw, canonical, note))
            cnt += 1
        except Exception as e:
            print(f"Error mapping {raw} -> {canonical}: {e}")
            
    # Also ensure canonicals exist in assets table to pass validation
    canonicals = set(m[1] for m in mappings)
    for c_id in canonicals:
        cursor.execute("""
            INSERT OR IGNORE INTO assets (asset_id, symbol_name, market, asset_type, index_role)
            VALUES (?, ?, 'CN', 'INDEX', 'MARKET')
        """, (c_id, c_id))
        
    conn.commit()
    conn.close()
    print(f"✅ inserted/updated {cnt} mappings in asset_symbol_map.")
    print("Ambiguity for '000300' and others should be resolved.")

if __name__ == "__main__":
    fix_ambiguous_indices()
