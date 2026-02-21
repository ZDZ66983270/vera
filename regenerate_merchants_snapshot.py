from engine.snapshot_builder import run_snapshot
from datetime import datetime

def regenerate():
    symbol = "CN:STOCK:600036" # Merchants Bank
    print(f"Regenerating snapshot for {symbol}...")
    
    # Run snapshot and SAVE to DB
    run_snapshot(symbol, save_to_db=True)
    
    print("Snapshot regeneration complete.")

if __name__ == "__main__":
    regenerate()
