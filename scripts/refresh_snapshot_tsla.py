from engine.snapshot_builder import run_snapshot
import sys
import os

# Ensure project root is in path
sys.path.append(os.getcwd())

if __name__ == "__main__":
    print("Updating TSLA snapshot...")
    try:
        res = run_snapshot("TSLA")
        print("Snapshot result:", res)
        print("Done.")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
