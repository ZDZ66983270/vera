
try:
    import pytesseract
    PYTESSERACT_AVAILABLE = True
except ImportError:
    PYTESSERACT_AVAILABLE = False

from PIL import Image, ImageOps, ImageFilter
import re
import io
import os

# Explicitly set tesseract path for macOS Homebrew
if PYTESSERACT_AVAILABLE and os.path.exists("/opt/homebrew/bin/tesseract"):
    pytesseract.pytesseract.tesseract_cmd = "/opt/homebrew/bin/tesseract"

def preprocess_image(image: Image.Image) -> Image.Image:
    """
    预处理图片以提高 OCR 识别率
    """
    # 转为灰度图
    gray = ImageOps.grayscale(image)
    # 增加对比度
    # gray = ImageOps.autocontrast(gray)
    # 二值化 (Thresholding) - 针对 Futubull 这种深色/浅色背景可能需要调整
    # 这里简单采用固定阈值或自动处理
    return gray

def extract_stock_data(image_bytes: bytes) -> dict:
    """
    核心 OCR 识别函数
    """
    if not PYTESSERACT_AVAILABLE:
        return {"error": "OCR 模块未安装。请安装 pytesseract 并配置 Tesseract-OCR 引擎以使用图片识别功能。"}

    image = Image.open(io.BytesIO(image_bytes))
    processed_img = preprocess_image(image)
    
    # 执行 OCR (指定中文简体 + 英文)
    # 注意：需要确保系统已安装 tesseract-lang (chi_sim)
    try:
        text = pytesseract.image_to_string(processed_img, lang='chi_sim+eng')
    except Exception as e:
        return {"error": f"OCR 引擎调用失败: {str(e)}"}

    print("--- OCR RAW START ---")
    print(text)
    print("--- OCR RAW END ---")

    data = {
        "symbol": None,
        "name": None,
        "price": None,
        "pe_ttm": None,
        "pb": None,
        "div_yield": None,
        "div_amount": None,
        "div_amount": None,
        "date": None,
        "open": None,
        "high": None,
        "low": None,
        "prev_close": None
    }
    
    # Pre-cleaning: Remove common OCR artifacts
    text = text.replace('O', '0')  # Common mistake

    # 尝试提取代码 (HK 5位)
    symbol_match = re.search(r'(\d{5})\s*HK', text)
    if not symbol_match:
        # 尝试 A 股 6 位
        symbol_match = re.search(r'(\d{6})\s*(SH|SS|SZ)', text)
    if not symbol_match:
        # 尝试美股指数 (.SPX, .NDX, .DJI) -> Yahoo Format
        # Relaxed: Optional dot, ignore case
        us_index_match = re.search(r'(?:^|\s|\.)(SPX|NDX|DJI)', text, re.I)
        if us_index_match:
            idx = us_index_match.group(1).upper()
            data["symbol"] = f"^{idx}"

    if symbol_match:
        data["symbol"] = symbol_match.group(1)
        if "HK" in text: data["symbol"] += ".HK"
        elif "SH" in text or "SS" in text: data["symbol"] += ".SH"
        elif "SZ" in text: data["symbol"] += ".SZ"

    # 提取价格
    # Support 1,234.56 OR 1234.56
    price_match = re.search(r'(\d{1,3}(?:,\d{3})*\.\d{2}|\d+\.\d{2})', text)
    if price_match:
        price_str = price_match.group(1).replace(',', '')
        data["price"] = float(price_str)

    # 提取 PE TTM (支持中文和英文关键词)
    pe_match = re.search(r'(?:市盈率|PE).*?TTM\s*(\d+\.\d{1,2})', text, re.I)
    if not pe_match:
        pe_match = re.search(r'PE\s*\(TTM\)\s*(\d+\.\d{1,2})', text, re.I)
    if pe_match:
        data["pe_ttm"] = float(pe_match.group(1))

    # 提取 PB
    pb_match = re.search(r'(?:市净率|PB)\s*(\d+\.\d{1,2})', text, re.I)
    if pb_match:
        data["pb"] = float(pb_match.group(1))

    # 提取股息率 % (Dividend Yield)
    div_yield_match = re.search(r'(?:股息率|Div\s*Yield).*?(\d+\.\d{1,2})%', text, re.I)
    if div_yield_match:
        data["div_yield"] = float(div_yield_match.group(1)) / 100.0

    # 提取股息金额 (Dividend Amount per share)
    div_amt_match = re.search(r'(?:股息|Div\s*Amount).*?TTM\s*(\d+\.\d{1,3})(?!%)', text, re.I)
    if div_amt_match:
        data["div_amount"] = float(div_amt_match.group(1))

    # 提取日期 (12/22 16:00 美东)
    date_match = re.search(r'(\d{1,2})/(\d{1,2})\s+(\d{1,2}:\d{2})', text)
    if date_match:
        month, day, time_str = date_match.groups()
        data["date"] = f"2025-{month.zfill(2)}-{day.zfill(2)}"

    # 提取 OHLC (High, Low, Open, PrevClose)
    # Common OCR misreads:
    # 昨收价 -> PEWS, PEW, PENS
    # 开盘价 -> 盘价, FAHY
    # 最高价 -> (Correct usually)
    # 最低价 -> (Correct usually)
    
    def extract_val(patterns, text):
        for pat in patterns:
            m = re.search(pat, text, re.I)
            if m:
                return float(m.group(1).replace(',', ''))
        return None

    # High
    data["high"] = extract_val([
        r'(?:最高价|High)\s*(\d{1,3}(?:,\d{3})*\.\d{2}|\d+\.\d{2})',
        r'最高\s*(\d{1,3}(?:,\d{3})*\.\d{2}|\d+\.\d{2})'
    ], text)

    # Low
    data["low"] = extract_val([
        r'(?:最低价|Low)\s*(\d{1,3}(?:,\d{3})*\.\d{2}|\d+\.\d{2})',
        r'最低\s*(\d{1,3}(?:,\d{3})*\.\d{2}|\d+\.\d{2})'
    ], text)

    # Open
    data["open"] = extract_val([
        r'(?:开盘价|Open)\s*(\d{1,3}(?:,\d{3})*\.\d{2}|\d+\.\d{2})',
        r'(?:盘价|FAHY)\s*(\d{1,3}(?:,\d{3})*\.\d{2}|\d+\.\d{2})',
        r'开盘\s*(\d{1,3}(?:,\d{3})*\.\d{2}|\d+\.\d{2})'
    ], text)

    # Prev Close
    data["prev_close"] = extract_val([
        r'(?:昨收价|Prev)\s*(\d{1,3}(?:,\d{3})*\.\d{2}|\d+\.\d{2})',
        r'(?:PEWS|PEW|PENS)\s*(\d{1,3}(?:,\d{3})*\.\d{2}|\d+\.\d{2})',
        r'昨收\s*(\d{1,3}(?:,\d{3})*\.\d{2}|\d+\.\d{2})'
    ], text)

    return data
