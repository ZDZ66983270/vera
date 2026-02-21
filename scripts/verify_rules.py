import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from engine.snapshot_builder import run_snapshot
from db.connection import get_connection

ASSETS = ["US:TSLA", "US:MSFT", "HK:00700", "US:BABA"]

def verify():
    print(f"{'Asset':<10} | {'ValKey':<15} | {'Quad':<5} | {'Action':<20} | {'Suggestion':<20}")
    print("-" * 80)
    
    for symbol in ASSETS:
        try:
            # Run snapshot (no save)
            data = run_snapshot(symbol, save_to_db=False)
            
            val_key = data.value.get('valuation_status_key', 'N/A')
            quad = data.risk_card.get('risk_quadrant', 'N/A')
            
            # Behavior info injected into overlay or main suggestion
            action_code = data.overlay.get('behavior_action_code', 'N/A')
            suggestion = data.behavior_suggestion
            
            print(f"{symbol:<10} | {val_key:<15} | {quad:<5} | {action_code:<20} | {suggestion:<20}")
            
        except Exception as e:
            print(f"{symbol:<10} | ERROR: {e}")

if __name__ == "__main__":
    verify()
