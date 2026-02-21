
import pandas as pd

# Mocking the structure from app.py
all_results = [
    {
        "status": "success",
        "msg": "识别完成：共提取 15 个指标(待确认)",
        "file_name": "22年半年报.pdf",
        "report_date": "2022-08-19",
        "metrics_count": 15,
        "extracted_data": {"revenue": 100, "net_profit": 50}
    },
    {
        "status": "success",
        "msg": "识别完成：共提取 14 个指标(待确认)",
        "file_name": "22年一季报.pdf",
        "report_date": "2022-03-31",
        "metrics_count": 14,
        "extracted_data": {"revenue": 80, "net_profit": 40}
    }
]

res = {
    "success": True,
    "msg": "已完成 2 个文件的处理。成功: 2, 失败: 0",
    "details": all_results
}

# Testing the logic from app.py
print(f"Details exists: {'details' in res}")
if "details" in res:
    details_df = pd.DataFrame(res["details"])
    print("DataFrame Head:")
    print(details_df.head())
    
    has_extracted_data = any("extracted_data" in d for d in res["details"])
    print(f"Has extracted_data in details: {has_extracted_data}")
    
    for idx, d in enumerate(res["details"]):
        print(f"Item {idx} keys: {list(d.keys())}")
        print(f"Has extracted_data: {'extracted_data' in d}")
        if "extracted_data" in d and d["extracted_data"]:
             print(f" extracted_data items: {len(d['extracted_data'])}")
