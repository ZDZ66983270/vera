
import sqlite3
import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db.connection import get_connection

BACKUP_DB = "backups/vera_full_backup_20251229_172933/vera.db"

def merge_eps_bps_from_backup():
    """
    Merge EPS/BPS data from backup into current DB.
    Strategy: For each asset, take the most recent EPS/BPS from backup and update the most recent row in current DB.
    """
    if not os.path.exists(BACKUP_DB):
        print(f"Backup database not found: {BACKUP_DB}")
        return
        
    print("Connecting to databases...")
    current_conn = get_connection()
    backup_conn = sqlite3.connect(BACKUP_DB)
    
    current_cursor = current_conn.cursor()
    backup_cursor = backup_conn.cursor()
    
    # Get list of unique assets with EPS/BPS in backup
    print("Reading assets from backup...")
    backup_cursor.execute("""
        SELECT DISTINCT asset_id
        FROM financial_history
        WHERE eps_ttm IS NOT NULL OR bps IS NOT NULL
    """)
    assets = [row[0] for row in backup_cursor.fetchall()]
    
    print(f"Found {len(assets)} assets with EPS/BPS in backup")
    
    updated = 0
    not_found = 0
    
    for asset_id in assets:
        # Get most recent EPS/BPS from backup for this asset
        backup_cursor.execute("""
            SELECT eps_ttm, bps, dividend_amount, buyback_amount,
                   npl_ratio, provision_coverage, special_mention_ratio
            FROM financial_history
            WHERE asset_id = ?
            ORDER BY report_date DESC
            LIMIT 1
        """, (asset_id,))
        
        backup_row = backup_cursor.fetchone()
        if not backup_row:
            continue
            
        eps, bps, div_amt, buy_amt, npl_r, prov_c, sm_r = backup_row
        
        # Check if this asset exists in current DB
        current_cursor.execute("""
            SELECT report_date FROM financial_history 
            WHERE asset_id = ?
            ORDER BY report_date DESC
            LIMIT 1
        """, (asset_id,))
        
        current_row = current_cursor.fetchone()
        
        if current_row:
            report_date = current_row[0]
            # Update the most recent row with backup EPS/BPS
            current_cursor.execute("""
                UPDATE financial_history
                SET eps_ttm = ?,
                    bps = ?,
                    dividend_amount = COALESCE(?, dividend_amount),
                    buyback_amount = COALESCE(?, buyback_amount),
                    npl_ratio = COALESCE(?, npl_ratio),
                    provision_coverage = COALESCE(?, provision_coverage),
                    special_mention_ratio = COALESCE(?, special_mention_ratio)
                WHERE asset_id = ? AND report_date = ?
            """, (eps, bps, div_amt, buy_amt, npl_r, prov_c, sm_r, asset_id, report_date))
            updated += 1
            if updated <= 10:
                eps_str = f"{eps:.2f}" if eps else "N/A"
                print(f"  Updated {asset_id} @ {report_date}: EPS={eps_str}")
        else:
            not_found += 1
            if not_found <= 5:
                print(f"  Not found: {asset_id}")
    
    current_conn.commit()
    current_conn.close()
    backup_conn.close()
    
    print(f"\nMerge Complete:")
    print(f"  Updated: {updated} assets")
    print(f"  Not found in current DB: {not_found} assets")

if __name__ == "__main__":
    merge_eps_bps_from_backup()
