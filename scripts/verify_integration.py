import sys
import os
sys.path.append(os.getcwd())

from engine.snapshot_builder import run_snapshot

def verify_asset(symbol):
    print(f"\n--- Verifying {symbol} ---")
    try:
        data = run_snapshot(symbol, save_to_db=False)
        if not data:
            print("No data returned.")
            return

        q = data.quality
        if not q:
            print("No quality data found.")
            return

        print(f"Dividend Safety Level: {q.get('dividend_safety_level')}")
        print(f"Dividend Label: {q.get('dividend_safety_label_zh')}")
        print(f"Dividend Score: {q.get('dividend_safety_score')}")
        print(f"Dividend Notes: {q.get('dividend_notes')}")
        
        print(f"Earnings State: {q.get('earnings_state_code')}")
        print(f"Earnings Label: {q.get('earnings_state_label_zh')}")
        print(f"Earnings Desc: {q.get('earnings_state_desc_zh')}")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    # Test HSBC
    verify_asset("0005.HK")
    # Test TSLA
    verify_asset("TSLA")
