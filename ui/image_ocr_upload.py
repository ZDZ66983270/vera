
from utils.ocr_engine import extract_stock_data
import os
import json
from db.connection import get_connection

# Uploaded images paths (from previous context)
image_paths = [
    "/Users/zhangzy/.gemini/antigravity/brain/ca60efe7-715d-4bb1-afe9-0449a6767128/uploaded_image_0_1766467836881.png",
    "/Users/zhangzy/.gemini/antigravity/brain/ca60efe7-715d-4bb1-afe9-0449a6767128/uploaded_image_1_1766467836881.png",
    "/Users/zhangzy/.gemini/antigravity/brain/ca60efe7-715d-4bb1-afe9-0449a6767128/uploaded_image_2_1766467836881.png"
]

print("--- STARTING BATCH OCR ---")

results = []

for path in image_paths:
    print(f"\nProcessing: {os.path.basename(path)}")
    if not os.path.exists(path):
        print(f"File not found: {path}")
        continue
        
    try:
        with open(path, "rb") as f:
            data = extract_stock_data(f.read())
            
        if "error" in data:
            print(f"Error: {data['error']}")
        else:
            # Fix symbol if OCR confused it (e.g. .SPX) - handled in engine now
            # Fix source
            data['source'] = 'OCR_BACKEND_CONFIRM'
            results.append(data)
            
            print(f"Symbol: {data.get('symbol')}")
            print(f"Date:   {data.get('date')}")
            print(f"Price:  {data.get('price')}")
            print(f"Open:   {data.get('open')}")
            print(f"High:   {data.get('high')}")
            print(f"Low:    {data.get('low')}")
            print(f"Prev:   {data.get('prev_close')}")
            # print(json.dumps(data, indent=2, ensure_ascii=False))
            
    except Exception as e:
        print(f"Exception: {e}")

print("\n--- BATCH OCR COMPLETE ---")
print(f"Successfully extracted {len(results)} records.")

# Save results to a temp file for confirmation step
if results:
    with open("scripts/ocr_pending.json", "w") as f:
        json.dump(results, f, indent=2)
    print("Results saved to scripts/ocr_pending.json. Waiting for confirmation to write to DB.")
else:
    print("No valid results to save.")
