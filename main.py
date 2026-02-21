import sys
from engine.snapshot_builder import run_snapshot

if __name__ == "__main__":
    symbol = sys.argv[1] if len(sys.argv) > 1 else "TSLA"
    run_snapshot(symbol)
