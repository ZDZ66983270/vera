#!/usr/bin/env python3
"""
Test script to verify the evaluation history fix
"""
import sys
sys.path.insert(0, '/Users/zhangzy/My Docs/Privates/22-AI编程/VERA')

from utils.canonical_resolver import resolve_canonical_symbol
import sqlite3
import pandas as pd

def test_canonical_resolution():
    """Test if AAPL resolves correctly"""
    conn = sqlite3.connect('stock_analysis.db')
    
    test_codes = ['AAPL', 'TSLA', '00700', '600519']
    
    print("=== Testing Canonical ID Resolution ===\n")
    for code in test_codes:
        try:
            canonical_id = resolve_canonical_symbol(conn, code, strict_unknown=False)
            print(f"{code:10} -> {canonical_id}")
            
            # Check if snapshots exist
            cursor = conn.cursor()
            count = cursor.execute(
                'SELECT COUNT(*) FROM analysis_snapshot WHERE asset_id = ?', 
                (canonical_id,)
            ).fetchone()[0]
            print(f"           Found {count} snapshot(s)\n")
        except Exception as e:
            print(f"{code:10} -> ERROR: {e}\n")
    
    conn.close()

def test_get_asset_evaluation_history():
    """Test the modified function"""
    print("\n=== Testing get_asset_evaluation_history Function ===\n")
    
    # Import the function from app.py
    import importlib.util
    spec = importlib.util.spec_from_file_location("app", "/Users/zhangzy/My Docs/Privates/22-AI编程/VERA/app.py")
    app_module = importlib.util.module_from_spec(spec)
    
    # Mock streamlit
    import types
    st_mock = types.ModuleType('streamlit')
    st_mock.error = lambda x: print(f"ERROR: {x}")
    sys.modules['streamlit'] = st_mock
    
    try:
        spec.loader.exec_module(app_module)
        
        # Test with simplified code
        print("Testing with 'AAPL':")
        df = app_module.get_asset_evaluation_history('AAPL')
        print(f"  Returned {len(df)} records")
        if not df.empty:
            print(f"  Columns: {list(df.columns)}")
            print(f"  Sample:\n{df.head()}")
        else:
            print("  No records found (DataFrame is empty)")
            
    except Exception as e:
        print(f"Error testing function: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    test_canonical_resolution()
    test_get_asset_evaluation_history()
