
import os
import io
import re
from datetime import datetime
from typing import Dict, Any, List, Optional
from PIL import Image

from utils.ocr_engine import extract_stock_data
from utils.pdf_engine import PDFFinancialParser
from utils.financial_accumulator import FinancialAccumulator
from db.connection import get_connection

class BatchImageProcessor:
    """
    Unified Processor for Financial Reports (PDF/Images)
    Automates extraction and DB import for Quality Assessment support.
    """
    
    def __init__(self):
        self.logs = []

    def log(self, msg: str):
        print(f"[Processor] {msg}")
        self.logs.append(msg)

    def process_single_image(self, file: Any, asset_id: str, auto_save: bool = False, data_source: str = 'IMAGE_OCR') -> Dict[str, Any]:
        """
        Process a single image or PDF file. 
        auto_save: If True, writes to DB immediately. Default False for manual review.
        """
        filename = file.name
        is_pdf = filename.lower().endswith('.pdf')
        
        try:
            metrics = {}
            debug_logs = []
            if is_pdf:
                # 1. Use PDFFinancialParser for direct PDF extraction
                from utils.pdf_engine import PDFPLUMBER_AVAILABLE
                if not PDFPLUMBER_AVAILABLE:
                    return {"status": "error", "msg": "PDF 解析模块 pdfplumber 未安装，无法处理 PDF 文件。请安装后重试。", "file_name": filename}

                temp_path = f"temp_{filename}"
                with open(temp_path, "wb") as f:
                    f.write(file.getvalue())
                
                parser = PDFFinancialParser(pdf_path=temp_path, asset_id=asset_id)
                metrics = parser.parse_financials()
                debug_logs = metrics.get('debug_logs', [])
                os.remove(temp_path)
            else:
                # 2. Use OCR for images
                ocr_data = extract_stock_data(file.getvalue())
                debug_logs = [f"OCR Step 1: Stock Page Check..."]
                
                if ocr_data.get('pe_ttm') or ocr_data.get('pb'):
                    metrics = ocr_data
                    metrics['revenue'] = None 
                    metrics['net_profit'] = ocr_data.get('net_profit')
                    debug_logs.append("Identified as Stock Snapshot Page")
                else:
                    debug_logs.append("No stock headers found. Falling back to Full Table OCR...")
                    from utils.ocr_engine import PYTESSERACT_AVAILABLE
                    if not PYTESSERACT_AVAILABLE:
                         return {"status": "error", "msg": "OCR 模块未安装，无法执行表格识别。请安装 pytesseract。", "file_name": filename}
                    
                    import pytesseract
                    image = Image.open(io.BytesIO(file.getvalue()))
                    text = pytesseract.image_to_string(image, lang='chi_sim+eng')
                    
                    parser = PDFFinancialParser(text_content=text, asset_id=asset_id)
                    metrics = parser.parse_financials()
                    debug_logs = metrics.get('debug_logs', [])

            # 3. Clean up metrics 
            if not metrics or metrics.get('error'):
                err_msg = metrics.get('error', "未能从文档中提取到有效指标（营收、利润等）。")
                return {"status": "error", "msg": err_msg, "file_name": filename, "debug": debug_logs}

            # Unpack tuples/lists for all metrics
            cleaned_metrics = {}
            for k, v in metrics.items():
                if v is None or k == 'debug_logs': continue
                if isinstance(v, (list, tuple)):
                    cleaned_metrics[k] = v[0] if len(v) > 0 else None
                else:
                    cleaned_metrics[k] = v
            metrics = cleaned_metrics

            # Normalize report_date
            report_date = metrics.get('report_date')
            if not report_date:
                report_date = datetime.now().strftime("%Y-12-31") # Placeholder

            # 4. Save to Database (Conditional)
            if auto_save:
                save_source = f"{data_source} ({filename})"
                self.save_metrics_to_db(asset_id, report_date, metrics, save_source)
            
            # Filter out None values for UI display
            extracted_summary = {k: v for k, v in metrics.items() if v is not None and v != [] and k not in ['debug_logs', 'raw_text']}

            return {
                "status": "success",
                "msg": f"识别完成：共提取 {len(extracted_summary)} 个指标" + (" (已自动保存)" if auto_save else " (待确认)"),
                "file_name": filename,
                "asset_id": asset_id,
                "report_date": report_date,
                "metrics_count": len(extracted_summary),
                "extracted_data": extracted_summary,
                "raw_text": metrics.get("raw_text"),
                "debug": debug_logs,
                "confidence": 0.85
            }

        except Exception as e:
            return {"status": "error", "msg": f"处理异常: {str(e)}", "file_name": filename}

    def save_metrics_to_db(self, asset_id: str, report_date: str, metrics: Dict[str, Any], data_source: str) -> Dict[str, Any]:
        """
        Public method to persist identified metrics to DB.
        Returns: {"status": "success"|"skipped"|"error", "msg": "..."}
        """
        conn = get_connection()
        try:
            cursor = conn.cursor()
            
            # Map parser fields to database columns
            db_map = {
                # Income Statement
                "revenue": "revenue_ttm",
                "net_profit": "net_profit_ttm",
                "eps": "eps_ttm",
                
                # Bank-specific Income
                "net_interest_income": "net_interest_income",
                "net_fee_income": "net_fee_income",
                "provision_expense": "provision_expense",
                
                # Asset Quality
                "total_loans": "total_loans",
                "loan_loss_allowance": "loan_loss_allowance",
                "npl_balance": "npl_balance",
                "npl_ratio": "npl_ratio",
                "provision_coverage": "provision_coverage",
                "core_tier1_ratio": "core_tier1_capital_ratio",  # Fixed: correct DB column name
                
                # Balance Sheet
                "total_assets": "total_assets",  # Added
                "total_liabilities": "total_liabilities",  # Added
                "common_equity_begin": "common_equity_begin",
                "common_equity_end": "common_equity_end",
                
                # Share Data
                "dividends_paid": "dividends_paid",
                "dividend_per_share": "dps",
                "shares_outstanding": "shares_outstanding",
                "shares_diluted": "shares_diluted",
                "treasury_shares": "treasury_shares",
                
                # Cash Flow & Debt
                "operating_cashflow": "operating_cash_flow",
                "cash_and_equivalents": "cash_and_equivalents",
                "total_debt": "total_debt"
            }
                
            # 数据源优先级检查
            SOURCE_PRIORITY = {
                "PDF_OCR_HIGH": 1.0,
                "PDF_OCR_MEDIUM": 0.85,
                "CSV_IMPORT": 0.7,
                "IMAGE_OCR": 0.6
            }
            current_confidence = SOURCE_PRIORITY.get(data_source, 0.5)
            
            # 检查是否已存在更高优先级数据
            cursor.execute("""
                SELECT data_source FROM financial_fundamentals 
                WHERE asset_id = ?
            """, (asset_id,))
            existing = cursor.fetchone()
            if existing:
                existing_source = existing[0]
                existing_confidence = SOURCE_PRIORITY.get(existing_source, 0.5)
                if existing_confidence > current_confidence:
                    msg = f"跳过：已存在更高优先级数据 ({existing_source} vs {data_source})"
                    self.log(msg)
                    return {"status": "skipped", "msg": msg}
            
            # 累计值转换为单季度
            accumulator = FinancialAccumulator()
            quarterly_metrics = accumulator.convert_to_quarterly(
                conn, asset_id, report_date, metrics
            )
            
            # No auto-calculation - Only extract what's in the report
            
            data_to_store = {}
            for k, db_col in db_map.items():
                val = quarterly_metrics.get(k)
                if val is not None:
                    if isinstance(val, (list, tuple)):
                         data_to_store[db_col] = val[0]
                    else:
                         data_to_store[db_col] = val
            
            if not data_to_store:
                return {"status": "skipped", "msg": "没有有效的数据需要保存 (No valid metrics found)"}

            if 'net_profit_ttm' in data_to_store and 'net_income_ttm' not in data_to_store:
                data_to_store['net_income_ttm'] = data_to_store['net_profit_ttm']

            # 1. Update financial_history
            cursor.execute("PRAGMA table_info(financial_history)")
            fh_actual_cols = [r[1] for r in cursor.fetchall()]
            fh_data = {k: v for k, v in data_to_store.items() if k in fh_actual_cols and v is not None}
            
            debug_info = []

            if fh_data:
                fh_cols = ["asset_id", "report_date"] + list(fh_data.keys())
                fh_placeholders = ", ".join(["?"] * len(fh_cols))
                fh_vals = [asset_id, report_date] + list(fh_data.values())
                fh_update = ", ".join([f"{k} = excluded.{k}" for k in fh_data.keys()])
                
                sql_fh = f"""
                    INSERT INTO financial_history ({', '.join(fh_cols)})
                    VALUES ({fh_placeholders})
                    ON CONFLICT(asset_id, report_date) DO UPDATE SET {fh_update}
                """
                cursor.execute(sql_fh, fh_vals)
                debug_info.append(f"History table: {len(fh_data)} columns updated.")
            else:
                 debug_info.append("History table: 0 columns updated (DB Schema limitation?)")
            
            # 2. Update financial_fundamentals
            cursor.execute("PRAGMA table_info(financial_fundamentals)")
            ff_actual_cols = [r[1] for r in cursor.fetchall()]
            ff_data = {k: v for k, v in data_to_store.items() if k in ff_actual_cols and v is not None}
            
            if ff_data:
                ff_cols = ["asset_id", "as_of_date", "data_source"] + list(ff_data.keys())
                ff_placeholders = ", ".join(["?"] * len(ff_cols))
                ff_vals = [asset_id, report_date, data_source] + list(ff_data.values())
                ff_update = ", ".join([f"{k} = excluded.{k}" for k in ff_data.keys()])
                
                sql_ff = f"""
                    INSERT INTO financial_fundamentals ({', '.join(ff_cols)})
                    VALUES ({ff_placeholders})
                    ON CONFLICT(asset_id) DO UPDATE SET {ff_update}, as_of_date=excluded.as_of_date, data_source=excluded.data_source
                """
                cursor.execute(sql_ff, ff_vals)
            
            conn.commit()
            return {
                "status": "success", 
                "msg": "Data saved successfully", 
                "details": f"History: {len(fh_data)} fields, Fund: {len(ff_data)} fields. ({', '.join(debug_info)})"
            }
            
        except Exception as e:
            return {"status": "error", "msg": str(e)}
        finally:
            conn.close()
