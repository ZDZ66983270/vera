
import sys
import os
sys.path.append(os.getcwd())

from engine.universe_manager import add_to_universe
from db.connection import get_connection

def verify_save():
    conn = get_connection()
    c = conn.cursor()
    
    # Clean up previous test
    c.execute("DELETE FROM asset_universe WHERE asset_id='TEST_SAVE_FIX'")
    c.execute("DELETE FROM asset_classification WHERE asset_id='TEST_SAVE_FIX'")
    c.execute("DELETE FROM assets WHERE asset_id='TEST_SAVE_FIX'")
    conn.commit()
    
    print("--- Test 1: Saving Sector without Scheme (Should fail/skip before fix, Succeed after fix) ---")
    try:
        # Simulate user input: Empty scheme, but provided sector
        canonical_id = add_to_universe(
            raw_symbol="TEST_SAVE_FIX",
            name="Test Asset",
            market="US",
            asset_type="EQUITY",
            scheme=None,  # Empty scheme from UI
            sector_code="10",
            sector_name="Test Sector",
            industry_name="Test Industry"
        )
        
        print(f"DEBUG: Returned Canonical ID: {canonical_id}")
        
        # Verify classification
        row = c.execute("""
            SELECT scheme, sector_name, industry_name 
            FROM asset_classification 
            WHERE asset_id=?
        """, (canonical_id,)).fetchone()
        
        if row:
            print(f"SUCCESS: Classification saved: {row}")
            if row[0] == 'GICS' and row[1] == 'Test Sector':
                print("PASS: Scheme defaulted to GICS and Sector saved.")
            else:
                print("FAIL: Content mismatch.")
        else:
            print("FAIL: No classification record found (Logic skipped saving).")

    except Exception as e:
        print(f"ERROR: {e}")
        
    print("\n--- Test 2: Saving with NAME ONLY (No Codes) ---")
    try:
        # Simulate user input: Names provided, but NO codes
        canonical_id_2 = add_to_universe(
            raw_symbol="TEST_SAVE_NAMES_ONLY",
            name="Test Name Only",
            market="US",
            asset_type="EQUITY",
            scheme="GICS",
            sector_code=None,
            sector_name="Information Technology",
            industry_code=None,
            industry_name="Semiconductors"
        )
        
        row2 = c.execute("""
            SELECT scheme, sector_name, industry_name 
            FROM asset_classification 
            WHERE asset_id=?
        """, (canonical_id_2,)).fetchone()
        
        if row2:
            print(f"SUCCESS: Classification saved for Names Only: {row2}")
        else:
            print("FAIL: Names Only - No classification record found.")

    except Exception as e:
        print(f"ERROR Test 2: {e}")

    finally:
        # Clean up
        c.execute("DELETE FROM asset_universe WHERE asset_id='TEST_SAVE_FIX'")
        c.execute("DELETE FROM asset_classification WHERE asset_id='TEST_SAVE_FIX'")
        c.execute("DELETE FROM assets WHERE asset_id='TEST_SAVE_FIX'")
        c.execute("DELETE FROM asset_universe WHERE asset_id='TEST_SAVE_NAMES_ONLY'")
        c.execute("DELETE FROM asset_classification WHERE asset_id='TEST_SAVE_NAMES_ONLY'")
        c.execute("DELETE FROM assets WHERE asset_id='TEST_SAVE_NAMES_ONLY'")
        conn.commit()
        conn.close()

if __name__ == "__main__":
    verify_save()
