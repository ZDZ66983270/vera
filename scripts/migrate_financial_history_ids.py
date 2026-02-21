
import sqlite3
import re

DB_PATH = "vera.db"

def resolve_to_canonical(symbol):
    symbol = symbol.strip().upper()
    if not symbol: return None
    
    # 1. Already Canonical?
    if symbol.startswith("HK:STOCK:") or symbol.startswith("US:STOCK:") or symbol.startswith("CN:STOCK:") or symbol.startswith("CN:INDEX:") or symbol.startswith("US:INDEX:") or symbol.startswith("HK:INDEX:") or symbol.startswith("HK:ETF:"):
        return symbol
        
    # 2. HK Logic (.HK)
    if symbol.endswith(".HK"):
        code = symbol.replace(".HK", "").strip()
        if code.isdigit():
            # Pad to 5 digits
            code = code.zfill(5)
            return f"HK:STOCK:{code}"
            
    # 3. CN Logic (.SH/.SS/.SZ)
    if symbol.endswith(".SH") or symbol.endswith(".SS"):
        code = symbol.replace(".SH", "").replace(".SS", "")
        if code.isdigit() and len(code) == 6:
            # 51xxxx -> ETF usually, 60xxxx -> STOCK, 000xxx -> INDEX
            # Heuristic for generic migration: assume STOCK mostly, or check pattern
            if code.startswith("000"): return f"CN:INDEX:{code}" # e.g. 000001.SH (Index) but wait, Ping An is 000001.SZ
            # Wait, 000001.SS is Index, 000001.SZ is Ping An
            if code.startswith("51") or code.startswith("58"): return f"CN:ETF_SH:{code}" # Simple heuristic
            return f"CN:STOCK:{code}"
            
    if symbol.endswith(".SZ"):
        code = symbol.replace(".SZ", "")
        if code.isdigit() and len(code) == 6:
             if code.startswith("15") or code.startswith("16"): return f"CN:ETF_SZ:{code}"
             return f"CN:STOCK:{code}"
             
    # 4. US Logic (No suffix, alphanumeric)
    # Exclude special chars usually
    if re.match(r'^[A-Z\.-]+$', symbol):
        # Could be ETF or STOCK. Default to STOCK for safety, or check if mapped in assets?
        # We can't easily know ETF vs STOCK without context, but let's assume STOCK for common ones
        return f"US:STOCK:{symbol}"

    return None

def migrate_ids():
    print("Starting Financial History ID Migration...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get all distinct asset_ids from financial_history
    cursor.execute("SELECT DISTINCT asset_id FROM financial_history")
    rows = cursor.fetchall()
    
    updates = 0
    failures = 0
    skips = 0
    
    for row in rows:
        old_id = row[0]
        new_id = resolve_to_canonical(old_id)
        
        if not new_id:
            print(f"  [SKIP] Could not resolve: {old_id}")
            failures += 1
            continue
            
        if new_id == old_id:
            skips += 1
            continue
            
        print(f"  [MIGRATE] {old_id} -> {new_id}")
        
        try:
            # Update records
            cursor.execute("UPDATE financial_history SET asset_id = ? WHERE asset_id = ?", (new_id, old_id))
            updates += 1
        except sqlite3.IntegrityError:
            # Target ID already exists (duplicate data). Delete the old ID record.
            cursor.execute("DELETE FROM financial_history WHERE asset_id = ?", (old_id,))
            print(f"  [MERGE] {new_id} already exists. Deleted {old_id}.")
            updates += 1
        except Exception as e:
            print(f"  [ERROR] {old_id} -> {new_id}: {e}")
            failures += 1

    conn.commit()
    conn.close()
    print(f"\nMigration Complete. Updated: {updates}, Skipped: {skips}, Failed: {failures}")

if __name__ == "__main__":
    migrate_ids()
