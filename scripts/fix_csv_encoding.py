import csv

# Data to write
data = [
    ["asset_id", "scheme", "sector_code", "sector_name", "industry_code", "industry_name", "benchmark_etf", "benchmark_index", "as_of_date", "is_active"],
    ["# --- US Stocks (GICS) ---", "", "", "", "", "", "", "", "", ""],
    ["AAPL", "GICS", "45", "Information Technology", "", "", "", "", "2020/1/1", "1"],
    ["MSFT", "GICS", "45", "Information Technology", "", "", "", "", "2020/1/1", "1"],
    ["TSLA", "GICS", "25", "Consumer Discretionary", "", "", "", "", "2020/1/1", "1"],
    ["BAC", "GICS", "40", "Financials", "", "", "", "", "2020/1/1", "1"],
    ["XOM", "GICS", "10", "Energy", "", "", "", "", "2020/1/1", "1"],
    ["# --- HK Stocks (Custom) ---", "", "", "", "", "", "", "", "", ""],
    ["00700.HK", "GICS", "50", "Communication Services", "MEDIA", "Media & Entertainment", "159751", "恒生科技指数", "2025/1/1", "1"],
    ["09988.HK", "GICS_CUSTOM", "25", "Consumer Discretionary", "HK_TECH", "HK Tech Leaders", "", "", "2020/1/1", "1"],
    ["00005.HK", "GICS_CUSTOM", "40", "Financials", "HK_BLUE", "HK Blue Chips", "", "", "2020/1/1", "1"],
    ["00998.HK", "GICS", "40", "Financials", "BANKS", "Banks", "513190", "恒生中国企业指数", "2025/1/1", "1"],
    ["01919.HK", "GICS", "20", "Industrials", "TRANSPORT", "Transportation", "", "恒生沪深港通指数", "2025/1/1", "1"],
    ["# --- CN Stocks (Custom) ---", "", "", "", "", "", "", "", "", ""],
    ["600030.SH", "GICS_CUSTOM", "40", "Financials", "CN_SEC", "Securities", "", "", "2025/1/1", "1"],
    ["600309.SH", "GICS", "15", "Materials", "CHEM", "Chemicals", "516020", "上证50指数", "2025/1/1", "1"],
    ["600536.SH", "GICS", "45", "Information Technology", "SOFTWARE", "Software & Services", "159852", "中证500指数", "2025/1/1", "1"],
    ["601519.SH", "GICS_CUSTOM", "40", "Financials", "CN_FIN", "Fintech Services", "", "", "2025/1/1", "1"],
    ["601919.SH", "GICS", "20", "Industrials", "TRANSPORT", "Transportation", "159662", "上证50指数", "2025/1/1", "1"],
    ["601998.SH", "GICS", "40", "Financials", "BANKS", "Banks", "512800", "沪深300指数", "2025/1/1", "1"],
]

# Write with UTF-8 BOM 
with open('imports/asset_classification.csv', 'w', encoding='utf-8-sig', newline='') as f:
    writer = csv.writer(f)
    writer.writerows(data)

print("✅ CSV file written with UTF-8-BOM encoding")
