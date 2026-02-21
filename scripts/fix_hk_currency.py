
import sqlite3
import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db.connection import get_connection

def fix_hk_currency():
    conn = get_connection()
    cursor = conn.cursor()
    
    print("Fixing HK Asset Currency Defaults...")
    
    # Known Mainland Companies (Reporting in CNY)
    # Copied from fetch_fundamentals.py
    known_cny_reporters = [
        "00700", "09988", "03690", "09618", "01024", "01810", # Tech
        "03988", "01398", "00939", "01288", "01658", "00998", # Banks
        "00883", "00857", "00386", # Energy
        "02318", "02628", # Insurance
        "02020", "02331", # Sport
        "06060", "09999", "01919"  # Others
    ]
    
    # Get all HK assets in financial_history
    cursor.execute("SELECT DISTINCT asset_id FROM financial_history WHERE asset_id LIKE 'HK:%'")
    hk_assets = cursor.fetchall()
    
    updated_count = 0
    
    for row in hk_assets:
        asset_id = row[0]
        raw_code = asset_id.split(":")[-1]
        
        is_mainland = False
        # Check Known List
        if any(cik in raw_code for cik in known_cny_reporters):
            is_mainland = True
            
        # Check Dual Listing (heuristic search in assets/universe not perfectly easy here, skipping for now, relying on list + non-default)
        # Actually, let's assume if it's NOT in our known 'Mainland' list, it is likely 'HKD'.
        # This is safe because we defaulted everything to 'CNY'. 
        # So we only need to flip the 'False Negatives' (Non-Mainland stocks labeled as CNY).
        
        if not is_mainland:
            # Check current currency
            cursor.execute("SELECT currency FROM financial_history WHERE asset_id = ? LIMIT 1", (asset_id,))
            curr = cursor.fetchone()[0]
            
            if curr == 'CNY':
                print(f"Update {asset_id}: CNY -> HKD (Assumed Local/USD)")
                cursor.execute("UPDATE financial_history SET currency = 'HKD' WHERE asset_id = ?", (asset_id,))
                updated_count += 1
                
    conn.commit()
    conn.close()
    print(f"Fixed {updated_count} HK assets.")

if __name__ == "__main__":
    fix_hk_currency()
