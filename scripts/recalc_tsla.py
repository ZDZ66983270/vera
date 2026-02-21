
from engine.snapshot_builder import run_snapshot

if __name__ == "__main__":
    print("Triggering run_snapshot for TSLA...")
    data = run_snapshot("TSLA")
    print(f"Snapshot complete. Conclusion: {data.overall_conclusion}")
    if data and data.value:
         print(f"Valuation: PE={data.value.get('current_pe')}, PB={data.value.get('current_pb')}")
