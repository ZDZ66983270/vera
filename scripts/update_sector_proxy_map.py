import csv

# Updated sector proxy map data with new ETF mappings
data = [
    ["scheme", "sector_code", "sector_name", "proxy_etf_id", "market_index_id", "priority", "is_active", "note"],
    ["# --- US Sectors (GICS -> SPDR ETFs) ---", "", "", "", "", "", "", ""],
    ["GICS", "10", "Energy", "XLE", "^GSPC", "10", "1", "US sector proxy"],
    ["GICS", "15", "Materials", "XLB", "^GSPC", "10", "1", "US sector proxy"],
    ["GICS", "20", "Industrials", "XLI", "^GSPC", "10", "1", "US sector proxy"],
    ["GICS", "25", "Consumer Discretionary", "XLY", "^GSPC", "10", "1", "US sector proxy"],
    ["GICS", "30", "Consumer Staples", "XLP", "^GSPC", "10", "1", "US sector proxy"],
    ["GICS", "35", "Health Care", "XLV", "^GSPC", "10", "1", "US sector proxy"],
    ["GICS", "40", "Financials", "XLF", "^GSPC", "10", "1", "US sector proxy"],
    ["GICS", "45", "Information Technology", "XLK", "^GSPC", "10", "1", "US sector proxy"],
    ["GICS", "50", "Communication Services", "XLC", "^GSPC", "10", "1", "US sector proxy"],
    ["GICS", "55", "Utilities", "XLU", "^GSPC", "10", "1", "US sector proxy"],
    ["GICS", "60", "Real Estate", "XLRE", "^GSPC", "10", "1", "US sector proxy"],
    ["# --- HK Sectors (Custom -> ETFs) ---", "", "", "", "", "", "", ""],
    ["HK_USER", "HK_TECH", "HK Tech Leaders", "3033.HK", "HSTECH", "100", "1", "User custom mapping"],
    ["HK_USER", "HK_BLUE", "HK Blue Chips", "2800.HK", "HSI", "100", "1", "User custom mapping"],
    ["GICS", "50", "Communication Services", "159751", "恒生科技指数", "10", "1", "HK Tech ETF (Tencent sector)"],
    ["GICS", "40", "Financials", "513190", "恒生中国企业指数", "10", "1", "HK Financials ETF (Banks)"],
    ["GICS", "20", "Industrials", "", "恒生沪深港通指数", "10", "1", "HK Transportation (no specific ETF)"],
    ["# --- CN Sectors (Custom -> ETFs) ---", "", "", "", "", "", "", ""],
    ["GICS", "CN:SEC", "Securities", "CN:STOCK:512880", "沪深300指数", "10", "1", "CN Securities ETF"],
    ["GICS", "CN:FIN", "Fintech", "CN:STOCK:159851", "中证500指数", "10", "1", "CN Fintech ETF"],
    ["GICS", "40", "Financials", "512800", "沪深300指数", "10", "1", "CN Banks ETF"],
    ["GICS", "45", "Information Technology", "159852", "中证500指数", "10", "1", "CN Software ETF"],
    ["GICS", "15", "Materials", "516020", "上证50指数", "10", "1", "CN Chemicals ETF"],
    ["GICS", "20", "Industrials", "159662", "上证50指数", "10", "1", "CN Transportation ETF"],
]

# Write with UTF-8 BOM encoding
with open('imports/sector_proxy_map.csv', 'w', encoding='utf-8-sig', newline='') as f:
    writer = csv.writer(f)
    writer.writerows(data)

print("✅ sector_proxy_map.csv updated with new ETF mappings")
