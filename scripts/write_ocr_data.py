
import json
import os
from datetime import datetime
from data.price_cache import save_daily_price

# ❗ RED LINE: save_daily_price() auto-maps to canonical. Never bypass it.

PENDING_FILE = "scripts/ocr_pending.json"
DEFAULT_DATE = "2025-12-22"

if not os.path.exists(PENDING_FILE):
    print("No pending OCR data found.")
    exit(0)

with open(PENDING_FILE, "r") as f:
    records = json.load(f)

print(f"Found {len(records)} pending records.")
count = 0

for rec in records:
    # Validate
    if not rec.get('symbol') or not rec.get('price'):
        print(f"Skipping invalid record: {rec}")
        continue
        
    # Default Date
    trade_date = rec.get('date')
    if not trade_date:
        trade_date = DEFAULT_DATE
        print(f"Defaulting date to {trade_date} for {rec['symbol']}")
        
    # Construct DB Row
    # save_daily_price expecting: 
    # symbol, trade_date, open, high, low, close, volume, source
    # We only have Close. Open/High/Low = Close. Volume = 0.
    
    row = {
        "symbol": rec['symbol'],
        "trade_date": trade_date,
        "open": rec.get('open') or rec['price'],
        "high": rec.get('high') or rec['price'],
        "low": rec.get('low') or rec['price'],
        "close": rec['price'],
        "volume": 0,
        "source": "OCR_BACKEND"
    }
    
    try:
        save_daily_price(row)
        print(f"Saved {rec['symbol']} Price: {rec['price']} Date: {trade_date}")
        count += 1
    except Exception as e:
        print(f"Failed to save {rec['symbol']}: {e}")

print(f"\nSuccessfully wrote {count} records to database.")

# Clean up
# os.remove(PENDING_FILE) # Optional: keep for debug or remove
print("Pending file preserved for safety. Delete manually if needed.")
