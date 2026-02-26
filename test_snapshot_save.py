import sqlite3
from engine.snapshot_builder import run_snapshot

symbol = 'HK:STOCK:03968'
# Run with save_to_db=True
print(f"Running snapshot for {symbol}...")
data = run_snapshot(symbol, save_to_db=True)

conn = sqlite3.connect('vera.db')
cursor = conn.cursor()
cursor.execute("SELECT * FROM quality_snapshot WHERE asset_id=? ORDER BY created_at DESC LIMIT 1", (symbol,))
row = cursor.fetchone()
cols = [d[0] for d in cursor.description]
conn.close()

if row:
    res = dict(zip(cols, row))
    print("Saved Quality Snapshot:")
    for k in ['dividend_safety_level', 'earnings_state_code', 'quality_buffer_level']:
        print(f"  {k}: {res.get(k)}")
else:
    print("No snapshot found.")
