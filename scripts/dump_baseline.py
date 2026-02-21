
import sys
import os
import json
import sqlite3
import pandas as pd
from datetime import datetime

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.snapshot_builder import run_snapshot
from analysis.dashboard import DashboardData
from config import DB_PATH

ASSETS = ["TSLA", "MSFT", "00700.HK", "BABA"]
OUTPUT_FILE = "scripts/baseline_dump.json"

def dump_baseline():
    results = {}
    print(f"Starting baseline dump for {len(ASSETS)} assets...")
    
    for symbol in ASSETS:
        print(f"\nProcessing {symbol}...")
        try:
            # Run snapshot to get fresh analysis data
            # We don't need to save to DB for verification, but it might be safer to keep consistent with app.py
            # app.py calls run_snapshot(symbol, save_to_db=False) usually for view only?
            # Actually Main Page calls run_snapshot(..., save_to_db=False)
            
            dashboard_data = run_snapshot(symbol, save_to_db=False)
            
            if not dashboard_data:
                print(f"Failed to get dashboard data for {symbol}")
                continue

            # Extract key metrics
            # 1. Quadrant (risk_card.quadrant)
            quadrant = "N/A"
            if dashboard_data.risk_card:
                quadrant = dashboard_data.risk_card.get("risk_quadrant", "N/A")
            
            # 2. Valuation Status
            # dashboard_data.value["valuation_status"]
            val_status = dashboard_data.value.get("valuation_status", "N/A")
            
            # 3. Behavior Action/Suggestion
            # dashboard_data.behavior_suggestion
            behavior = dashboard_data.behavior_suggestion
            
            # 4. D-State (from path or risk_card)
            d_state = "N/A"
            if dashboard_data.path:
                d_state = dashboard_data.path.get("state", "N/A")
            
            results[symbol] = {
                "quadrant": quadrant,
                "valuation_status": val_status,
                "behavior_suggestion": behavior,
                "d_state": d_state,
                "timestamp": datetime.now().isoformat()
            }
            print(f"Captured: {results[symbol]}")
            
        except Exception as e:
            print(f"Error processing {symbol}: {e}")
            import traceback
            traceback.print_exc()

    # Save to file
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\nBaseline dump saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    dump_baseline()
