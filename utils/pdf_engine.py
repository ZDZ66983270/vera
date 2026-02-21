
try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False

import re
import pandas as pd
from typing import Dict, Any, Optional
from datetime import datetime
from config.bank_keywords import get_keywords_for_bank

class PDFFinancialParser:
    """
    Parser for Financial Report PDFs (Annual/Quarterly Reports)
    Extracts key metrics: Revenue, Net Profit, EPS, Dividend
    支持两种模式：1) PDF文件路径 2) 直接文本内容（来自OCR）
    """
    
    def __init__(self, pdf_path: Optional[str] = None, text_content: Optional[str] = None, asset_id: Optional[str] = None):
        """
        初始化解析器
        
        Args:
            pdf_path: PDF文件路径（传统模式）
            text_content: 直接文本内容（OCR模式）
            asset_id: 资产ID (如 "CN:STOCK:600036")，用于匹配特定关键词
        """
        if pdf_path is None and text_content is None:
            raise ValueError("必须提供pdf_path或text_content之一")
        
        self.pdf_path = pdf_path
        self.text_content = text_content or ""
        self.asset_id = asset_id
        self.tables = []
        self.logs = []
        
    def log(self, msg: str):
        print(f"[PDF_DEBUG] {msg}")
        self.logs.append(msg)
    
    def _detect_sector(self) -> str:
        """
        检测企业所属行业
        
        Returns:
            'bank' | 'generic' | 'insurance' | ...
        """
        # 方案1：基于 asset_id 判断（最可靠）
        if self.asset_id:
            # 银行列表（从 bank_keywords.py 导入）
            from config.bank_keywords import BANK_CODE_MAPPING
            if self.asset_id in BANK_CODE_MAPPING:
                self.log(f"Detected sector: BANK (based on asset_id: {self.asset_id})")
                return 'bank'
        
        # 方案2：基于文本内容判断（备用）
        # 银行特征关键词：不良贷款、拨备覆盖率、资本充足率
        bank_keywords = ["不良贷款", "拨备覆盖率", "资本充足率", "核心一级资本", "贷款减值准备"]
        if any(kw in self.text_content[:5000] for kw in bank_keywords):
            self.log("Detected sector: BANK (based on text content)")
            return 'bank'
        
        # 默认：通用企业
        self.log("Detected sector: GENERIC (default)")
        return 'generic'
    
    def _get_keywords(self, metric: str) -> list:
        """
        根据行业类型获取关键词
        
        Args:
            metric: 指标名称
        
        Returns:
            关键词列表
        """
        sector = self._detect_sector()
        
        if sector == 'bank':
            # 使用现有银行关键词（完全不变）
            from config.bank_keywords import get_keywords_for_bank
            return get_keywords_for_bank(self.asset_id, metric)
        
        elif sector == 'generic':
            # 使用新增通用企业关键词
            try:
                from config.generic_keywords import get_generic_keywords
                return get_generic_keywords(metric)
            except ImportError:
                self.log(f"Warning: generic_keywords not found, falling back to empty list for {metric}")
                return []
        
        else:
            # 未来扩展：保险、房地产等
            return []

    def extract_content(self, max_pages: int = 50):
        """
        1. Quick scan for important keywords (Segment Info, Quality, Financials)
        2. Extract with layout=True for better structural preservation.
        """
        if self.text_content: return
        
        if not PDFPLUMBER_AVAILABLE:
            raise ImportError("PDF 解析模块 pdfplumber 未安装，请安装后重试。")

        keywords = ["Segment Information", "分部信息", "经营分部", "不良贷款", "资产负债表", "利润表", "主要会计数据"]
        
        try:
            with pdfplumber.open(self.pdf_path) as pdf:
                full_text = []
                pages_to_scan = pdf.pages[:min(max_pages, len(pdf.pages))]
                
                self.log(f"Scanning first {len(pages_to_scan)} pages for key content...")
                
                for i, page in enumerate(pages_to_scan):
                    # Quick raw extract for keyword matching
                    raw_text = page.extract_text()
                    if not raw_text: continue
                    
                    # If it's a "hot page" (summary or segment), use layout=True
                    if any(kw in raw_text for kw in keywords):
                        self.log(f"  Hot page detected: Page {i+1}. Using layout-enhanced extraction.")
                        layout_text = page.extract_text(layout=True)
                        full_text.append(layout_text)
                    else:
                        # For regular pages, standard extract is enough to save processing
                        full_text.append(raw_text)
                
                self.text_content = "\n\n".join(full_text)
                self.log(f"Extraction complete: {len(self.text_content)} chars.")
                
        except Exception as e:
            self.log(f"Extraction failed: {e}")
            raise

    

    def parse_financials(self) -> Dict[str, Any]:
        """
        Parse key metrics using regex on extracted text
        """
        if not self.text_content:
            self.extract_content()
            
        self.log("--- Starting Financial Parsing ---")
        
        # 1. Global Unit Detection (Fallback)
        # Search deeper in header
        header_text = self.text_content[:15000] # Often "Data Summary" uses 10^8, but we want to know if Million exists
        
        global_unit = 1.0
        if any(x in header_text for x in ["百万元", "百萬元", "million", "In millions"]):
            global_unit = 1_000_000
            self.log("Detected Global Unit Preference: Millions (10^6)")
        elif any(x in header_text for x in ["亿元", "億元", "billion", "In billions"]):
            global_unit = 100_000_000
            self.log("Detected Global Unit Preference: 100M/亿 (10^8)")
        
        self.global_unit = global_unit
        
        # 1.5 Report Type Detection
        # Defaults to 'unknown' if no keywords found
        report_type = "unknown"
        if any(x in header_text for x in ["年度报告", "Annual Report", "ANNUAL REPORT"]):
            if "半年度" not in header_text and "Interim" not in header_text:
                report_type = "annual"
                self.log("Detected Report Type: Annual")
        elif any(x in header_text for x in ["半年度", "中期报告", "Interim Report", "INTERIM REPORT"]):
            report_type = "interim"
            self.log("Detected Report Type: Interim")
        elif any(x in header_text for x in ["季度报告", "Quarterly Report", "QUARTERLY REPORT", "第一季度", "第三季度"]):
            report_type = "quarterly"
            self.log("Detected Report Type: Quarterly")
            
        self.report_type = report_type
        
        # 2. Key Metrics Placeholder
        data = {
            # Income Statement
            "revenue": None,
            "net_interest_income": None,
            "net_fee_income": None,
            "provision_expense": None,
            "net_profit": None,
            "eps": None,
            "dividend": None,
            
            # Balance Sheet
            "total_loans": None,
            "loan_loss_allowance": None,
            "npl_balance": None,
            "npl_ratio": None,
            "common_equity_begin": None,
            "common_equity_end": None,
            "total_common_equity": None,  # Average or single period
            "total_assets": None,
            "total_liabilities": None,
            
            # Capital & Regulatory
            "provision_coverage": None,  # 拨备覆盖率
            "core_tier1_ratio": None,
            
            # Cash Flow & Dividends
            "dividends_paid": None,
            "dividend_per_share": None,
            "operating_cashflow": None,  # 新增：经营活动现金流
            
            # Balance Sheet - Cash & Debt
            "cash_and_equivalents": None,  # 新增：现金及等价物
            "total_debt": None,  # 新增：总债务
            
            # Share Structure
            "shares_outstanding": None,
            "shares_diluted": None,
            "treasury_shares": None,
            
            # Metadata
            "report_date": None,
            "raw_text": None,
            "debug_logs": self.logs,
            "report_type": self.report_type
        }

        
        # 2. Date Detection - Prioritize Accounting Period End Dates
        cn_years = {"二〇二三": "2023", "二〇二四": "2024", "二〇二五": "2025", "二〇二六": "2026"}
        cn_quarters = {
            "第一季度": "03-31", "第二季度": "06-30", "第三季度": "09-30", "第四季度": "12-31", 
            "第壹季度": "03-31", "第贰季度": "06-30", "第叁季度": "09-30", "第肆季度": "12-31",
            "一季度": "03-31", "半年度": "06-30", "三季度": "09-30",
            "年报": "12-31", "年度報告": "12-31", "年度报告": "12-31"
        }
        
        # Priority 1: Explicit period-end expressions (截至 YYYY年MM月DD日)
        period_end_match = re.search(r'截至\s*(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日', header_text)
        if period_end_match:
            y, m, d = period_end_match.groups()
            data['report_date'] = f"{y}-{int(m):02d}-{int(d):02d}"
            self.log(f"Detected period-end date (截至): {data['report_date']}")
        
        # Priority 2: Quarter keywords (YYYY年第X季度 / 半年度)
        if not data['report_date']:
            # Try to find year and quarter keywords together
            year_val = None
            q_val = None
            
            # Check for explicit year + quarter pattern
            for cn_year, en_year in cn_years.items():
                if cn_year in header_text:
                    year_val = en_year
                    break
            
            # Also check for numeric year
            if not year_val:
                year_match = re.search(r'(\d{4})\s*年', header_text[:500])
                if year_match:
                    year_val = year_match.group(1)
            
            # Find quarter keyword
            for cn_q, en_q in cn_quarters.items():
                if cn_q in header_text:
                    q_val = en_q
                    self.log(f"Detected quarter keyword: {cn_q} -> {q_val}")
                    break
            
            if year_val and q_val:
                data['report_date'] = f"{year_val}-{q_val}"
                self.log(f"Constructed date from year + quarter: {data['report_date']}")
        
        # Priority 3: Generic date pattern (fallback - may capture publication date)
        if not data['report_date']:
            date_match = re.search(r'(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日', self.text_content)
            if not date_match:
                 date_match = re.search(r'(\d{4})\s*年\s*(\d{1,2})\s*月', self.text_content)
                 
            if date_match:
                parts = date_match.groups()
                y = parts[0]
                m = int(parts[1])
                d = int(parts[2]) if len(parts) > 2 else 1
                data['report_date'] = f"{y}-{m:02d}-{d:02d}"
                self.log(f"Detected generic date (may be publication date): {data['report_date']}")


        # 3. Priority-Based Metric Extraction - Using Centralized Config
        
        # Helper for cleaner code - now uses sector-aware keyword retrieval
        def get_kws(metric):
            return self._get_keywords(metric)

        # 3.1 Total Assets & Liabilities
        data['total_assets'] = self._find_metric_prioritized(get_kws("total_assets"), is_large=True, strategy="nearest", metric_name="total_assets")
        data['total_liabilities'] = self._find_metric_prioritized(get_kws("total_liabilities"), is_large=True, strategy="nearest", metric_name="total_liabilities")

        # 3.2 Income Statement
        data['net_interest_income'] = self._find_metric_prioritized(get_kws("net_interest_income"), is_large=True, strategy="nearest", metric_name="net_interest_income")
        data['net_fee_income'] = self._find_metric_prioritized(get_kws("net_fee_income"), is_large=True, strategy="nearest", metric_name="net_fee_income")
        data['revenue'] = self._find_metric_prioritized(get_kws("revenue"), is_large=True, strategy="nearest", metric_name="revenue")
        data['provision_expense'] = self._find_metric_prioritized(get_kws("provision_expense"), is_large=True, metric_name="provision_expense")
        data['net_profit'] = self._find_metric_prioritized(get_kws("net_profit"), is_large=True, strategy="nearest", metric_name="net_profit")

        # 3.3 Balance Sheet Details
        data['total_loans'] = self._find_metric_prioritized(get_kws("total_loans"), is_large=True, metric_name="total_loans")
        data['loan_loss_allowance'] = self._find_metric_prioritized(get_kws("loan_loss_allowance"), is_large=True, metric_name="loan_loss_allowance")
        data['npl_balance'] = self._find_metric_prioritized(get_kws("npl_balance"), is_large=True, metric_name="npl_balance")
        data['npl_ratio'] = self._find_metric_prioritized(get_kws("npl_ratio"), is_large=False, strategy="nearest", metric_name="npl_ratio")

        data['common_equity_begin'] = self._find_metric_prioritized(get_kws("common_equity_begin"), is_large=True, metric_name="common_equity_begin")
        data['common_equity_end'] = self._find_metric_prioritized(get_kws("common_equity_end"), is_large=True, metric_name="common_equity_end")
        
        if data['common_equity_begin'] and data['common_equity_end']:
            data['total_common_equity'] = (data['common_equity_begin'] + data['common_equity_end']) / 2
        elif data['common_equity_end']:
            data['total_common_equity'] = data['common_equity_end']
        
        # 3.4 Regulatory & Capital
        data['provision_coverage'] = self._find_metric_prioritized(get_kws("provision_coverage"), is_large=False, strategy="nearest", metric_name="provision_coverage")
        data['core_tier1_ratio'] = self._find_metric_prioritized(get_kws("core_tier1_ratio"), is_large=False, strategy="nearest", metric_name="core_tier1_ratio")
        
        # 3.5 Dividends & Share Structure
        data['dividends_paid'] = self._find_metric_prioritized(get_kws("dividends_paid"), is_large=True, metric_name="dividends_paid")
        
        # DPS special handling: first find normalized val, then check for "per 10 shares" raw text
        res_dps = self._find_metric_prioritized(get_kws("dividend_per_share"), is_large=False, strategy="nearest", metric_name="dividend_per_share")
        dps_val = res_dps
        if dps_val is not None:
             ratio10 = re.search(r'每\s*10\s*股\s*派\s*(?:发现金红利|现金红利|现金)\s*([\d\.]+)\s*元', self.text_content)
             if ratio10:
                 r_val = float(ratio10.group(1))
                 self.log(f"Detected 'Per 10 Shares' dividend: {r_val} Yuan per 10. Normalizing to {r_val/10} per share.")
                 dps_val = r_val / 10.0
        data['dividend_per_share'] = dps_val
        data['dividend'] = dps_val 

        data['shares_outstanding'] = self._find_metric_prioritized(get_kws("shares_outstanding"), is_large=False, metric_name="shares_outstanding")
        if data['shares_outstanding'] and data['shares_outstanding'] < 500_000_000:
            # Heuristic: 
            # If expanding by 'Yi' (10^8) results in > 1 Trillion shares, it's likely 'Million' unit.
            # Example: 25,220 (Million) -> 2.5 Trillion if Yi -> Wrong. 25 Billion if Million -> Correct.
            val = data['shares_outstanding']
            as_yi = val * 100_000_000
            
            if as_yi > 1_000_000_000_000: # > 1 Trillion Shares is unrealistic (ICBC is ~350B)
                data['shares_outstanding'] = val * 1_000_000
                self.log(f"Shares raw {val} likely in Millions, converted to {data['shares_outstanding']}")
            else:
                data['shares_outstanding'] = as_yi
                self.log(f"Shares raw {val} likely in Yi, converted to {data['shares_outstanding']}")
        
        data['eps'] = self._find_metric_prioritized(get_kws("eps"), is_large=False, strategy="nearest", metric_name="eps")
        
        # 新增字段：现金流和债务
        data['operating_cashflow'] = self._find_metric_prioritized(get_kws("operating_cashflow"), is_large=True, strategy="nearest", metric_name="operating_cashflow")
        data['cash_and_equivalents'] = self._find_metric_prioritized(get_kws("cash_and_equivalents"), is_large=True, strategy="nearest", metric_name="cash_and_equivalents")
        data['total_debt'] = self._find_metric_prioritized(get_kws("total_debt"), is_large=True, strategy="largest", metric_name="total_debt")

        data["raw_text"] = self.text_content
        return data

    def _find_metric_prioritized(self, keyword_groups: list, is_large: bool, strategy: str = "nearest", metric_name: str = "") -> Optional[float]:
        """
        Returns normalized value (float)
        Now handles global_unit internally.
        """
        all_candidates = []
        for group in keyword_groups:
            # Pass metric_name down for targeted exclusion logic (like positive constraints)
            cands = self._get_candidates_for_keywords(group, is_large=is_large, metric_name=metric_name)
            if cands:
                all_candidates.extend(cands)
        
        if not all_candidates:
            return None

        # Normalize candidates before picking
        normalized_cands = []
        for val, local_scale, dist, kw_pos, val_pos in all_candidates:
            # Selection bias: prioritize candidates with local units for is_large metrics
            effective_dist = dist
            
            # Use local_scale if detected, else use global_unit (ONLY if it's a large amount/currency)
            scale = 1.0
            if is_large:
                if local_scale:
                    scale = local_scale
                    effective_dist = max(0, effective_dist - 50) # Bonus for local unit matching
                else:
                    scale = self.global_unit
                    effective_dist += 200 # Penalty for lack of specific unit context
            else:
                # For non-large metrics (ratios, EPS), we generally ignore currency-based local scales
                # to prevent mis-scaling (e.g. ratio followed by currency total in same table)
                scale = 1.0 
            
            norm_val = val * scale
            if abs(norm_val) > 1000:
                self.log(f"  [{metric_name}] Normalizing: Raw={val} * Scale={scale} -> Norm={norm_val}")
            
            # NOISE FILTER: For large metrics (Assets, Cash, Debt), value must be significant (>10 million)
            # This filters out footnote markers like '1', '2' that get parsed as 1 million
            if is_large and abs(norm_val) < 10_000_000:
                self.log(f"  [{metric_name}] Skipping small value for large metric: {norm_val} (Threshold: 10M)")
                continue

            normalized_cands.append((norm_val, scale, effective_dist, kw_pos, val_pos))

        # Selection Strategy
        if not normalized_cands:
            return None

        if strategy == "largest":
            normalized_cands.sort(key=lambda x: x[0], reverse=True)
            res = normalized_cands[0]
            self.log(f"  Selected Largest NormVal: {res[0]} (Dist: {res[2]})")
            return res[0]
        # DEFAULT: Nearest (Smallest effective distance)
        normalized_cands.sort(key=lambda x: x[2])
        res = normalized_cands[0]
        self.log(f"  Selected Best Match NormVal: {res[0]} (Effective Dist: {res[2]})")
        return res[0]

    def _get_candidates_for_keywords(self, keywords: list, is_large: bool = False, window_size: int = 250, metric_name: str = "") -> list:
        all_candidates = []
        
        # Scale metrics that MUST be positive (Assets, Loans, Cash, Equity, Shares)
        positive_only_metrics = {
            "total_assets", "total_liabilities", "cash_and_equivalents", "total_loans", 
            "loan_loss_allowance", "common_equity_begin", "common_equity_end", 
            "shares_outstanding", "total_debt", "short_term_debt", "long_term_debt"
        }
        
        for kw in keywords:
            # Noise-tolerant joiner for Chinese: allow spaces
            flex_kw = r"[\s]*".join([re.escape(c) for c in list(kw)]) if re.search(r'[\u4e00-\u9fff]', kw) else re.escape(kw)
            pattern = re.compile(flex_kw, re.I)
            
            for match in pattern.finditer(self.text_content):
                start_pos, end_pos = match.start(), match.end()
                self.log(f"  Keyword '{kw}' found at position {start_pos}")
                
                # Search window for numbers - slightly larger to catch units
                window = self.text_content[end_pos : end_pos + window_size + 50]
                
                # CONTEXT EXCLUSION: If the keyword is "现金及现金等价物" and prepended by "影响" or "变动"
                # it's usually "汇率变动对现金的影响", not the balance itself.
                pre_context_10 = self.text_content[max(0, start_pos-10) : start_pos].strip()
                pre_context_30 = self.text_content[max(0, start_pos-30) : start_pos].strip()
                
                if kw in ["现金及现金等价物", "现金及等价物", "Cash and cash equivalents"]:
                     if any(ex in pre_context_30 for ex in ["影响", "变动", "变动额", "增加额", "减少额", "净增加", "净减少", "净额"]):
                         self.log(f"  Skipping '{kw}' due to movement-context in prefix: '{pre_context_30}'")
                         continue
                
                # PREVENT NPL OVERLAP: "不良贷款余额" contains "贷款余额"
                if kw in ["贷款总额", "贷款余额", "发放贷款及垫款", "Loans"]:
                     if "不良" in pre_context_10:
                         self.log(f"  Skipping '{kw}' because it's prefixed by '不良'")
                         continue
                
                # Robust regex: allow optional spaces, full-width Parens, and negative sign
                num_matches = re.finditer(r'[\(（-]?\s*([\d,]+(?:\.[\d]+)?)\s*[\)）]?', window)
                
                for nm in num_matches:
                    full_text = nm.group(0) 
                    val_str = nm.group(1).replace(',', '') 
                    raw_start, raw_end = nm.start(), nm.end()
                    
                    # Detect negative from parentheses or leading dash at the VERY start
                    is_negative = full_text.strip().startswith('(') or full_text.strip().startswith('（') or full_text.strip().startswith('-')
                    
                    # POSITIVE RESTRAINT logic based on metric_name
                    # Only Net Profit and Cash Flow net changes can be negative.
                    if is_negative and metric_name in positive_only_metrics:
                         self.log(f"  [{metric_name}] Skipping negative candidate: {full_text}")
                         continue
                    
                    # NOTE INDEX FILTER: If number is 1-2 digits inside parentheses, it's likely a footnote, skip it
                    if (full_text.strip().startswith('(') or full_text.strip().startswith('（')) and len(val_str) <= 2:
                        continue

                    # DATE FILTER: skip YYYY-MM-DD
                    full_nm_context = window[max(0, raw_start-5):min(len(window), raw_end+10)]
                    if re.search(r'\d{4}[\.\-/]\d{1,2}[\.\-/]\d{1,2}', full_nm_context):
                        continue 

                    # YEAR CONTEXT FILTER: skip if followed by "年" or "Year"
                    post_context = window[raw_end:raw_end+5].strip()
                    if post_context.startswith("年") or post_context.lower().startswith("year"):
                        self.log(f"  Skipping year-like value: {full_text} (followed by '{post_context[:4]}')")
                        continue 
 
                    try:
                        val = float(val_str)
                        if is_negative:
                             val = -val
                             self.log(f"  Captured negative value: {full_text} -> {val}")
                        
                        dist = raw_start 
                        # Reference preference: If multiple candidates, prefer one with a decimal for EPS
                        if kw in ["EPS", "基本每股收益"] and "." not in val_str:
                            dist += 100 

                        # Calculate absolute position of the value in the full text
                        # (needed for local unit detection lookback)
                        value_pos = end_pos + raw_start
                        
                        # 1. Local Unit Detection: Look backwards from value position for unit declarations
                        # Search backward up to 800 chars for specific unit strings
                        lookback_range = self.text_content[max(0, value_pos-800) : value_pos]
                        
                        # Initialize local_scale to None (will be set if unit is detected)
                        local_scale = None
                        
                        # Priority 1: Direct proximity unit
                        context_tail = window[raw_end : raw_end + 15]
                        context_around = window[max(0, raw_start-30) : min(len(window), raw_end+50)]
                        
                        if any(x in context_around for x in ["百万元", "百萬元", "million", "Millions"]): 
                             local_scale = 1_000_000
                             self.log(f"  Proximity unit 'million' detected for {val_str}")
                        elif any(x in context_around for x in ["亿元", "億元", "billion", "Billions"]): 
                             local_scale = 100_000_000
                             self.log(f"  Proximity unit 'billion' detected for {val_str}")
                        
                        # Priority 2: Look further back for "Units: Millions" etc.
                        if not local_scale:
                            if any(x in lookback_range for x in ["百万元", "百萬元", "百万", "Million", "Millions"]):
                                # If both 百万 and 亿 exist in lookback, pick the LAST one encountered before value
                                m_pos = lookback_range.rfind("百万") or lookback_range.lower().rfind("million")
                                b_pos = lookback_range.rfind("亿") or lookback_range.lower().rfind("billion")
                                if m_pos > b_pos:
                                    local_scale = 1_000_000
                                    self.log(f"  Dynamic unit 'million' detected in lookback for {val_str}")
                                elif b_pos > m_pos:
                                    local_scale = 100_000_000
                                    self.log(f"  Dynamic unit 'billion' detected in lookback for {val_str}")
                        
                        
                        # Use local_scale if detected, else use global_unit preference
                        scale = 1.0
                        if is_large:
                            if local_scale:
                                # SMART UNIT DETECTION: Check if value already includes unit conversion
                                # If we detect "亿元" (100M) but value is already in billions (e.g., 293333000000),
                                # it means the value is already in base unit (元), don't apply scale again.
                                # 
                                # Logic:
                                # - If local_scale is 100M (亿) and value > 1B, value is likely already in 元
                                # - If local_scale is 100M (亿) and value < 10000, value is in 亿, needs conversion
                                # - If local_scale is 1M (百万) and value > 10M, value is likely already in 元
                                # - If local_scale is 1M (百万) and value < 100000, value is in 百万, needs conversion
                                
                                should_apply_scale = True
                                
                                if local_scale == 100_000_000:  # 亿元
                                    # If value is already > 1 billion (10^9), it's likely already in 元
                                    # Example: 293333000000 (2933.33亿) should NOT be multiplied again
                                    # But: 2933.33 SHOULD be multiplied
                                    if abs(val) > 1_000_000_000:  # > 10亿
                                        should_apply_scale = False
                                        self.log(f"  Smart unit: Value {val} already in base unit (元), not applying 亿 scale")
                                    else:
                                        self.log(f"  Smart unit: Value {val} in 亿, applying scale 100M")
                                
                                elif local_scale == 1_000_000:  # 百万元
                                    # If value is already > 10 million, it's likely already in 元
                                    if abs(val) > 10_000_000:  # > 1000万
                                        should_apply_scale = False
                                        self.log(f"  Smart unit: Value {val} already in base unit (元), not applying 百万 scale")
                                    else:
                                        self.log(f"  Smart unit: Value {val} in 百万, applying scale 1M")
                                
                                
                                scale = local_scale if should_apply_scale else 1.0
                            else:
                                # No local unit detected, use global_unit
                                # But ALSO apply smart detection for global_unit
                                should_apply_global_scale = True
                                
                                if self.global_unit == 100_000_000:  # 亿元
                                    if abs(val) > 1_000_000_000:  # > 10亿
                                        should_apply_global_scale = False
                                        self.log(f"  Smart unit (global): Value {val} already in base unit (元), not applying global 亿 scale")
                                    else:
                                        self.log(f"  Smart unit (global): Value {val} in 亿, applying global scale 100M")
                                
                                elif self.global_unit == 1_000_000:  # 百万元
                                    if abs(val) > 10_000_000:  # > 1000万
                                        should_apply_global_scale = False
                                        self.log(f"  Smart unit (global): Value {val} already in base unit (元), not applying global 百万 scale")
                                    else:
                                        self.log(f"  Smart unit (global): Value {val} in 百万, applying global scale 1M")
                                
                                scale = self.global_unit if should_apply_global_scale else 1.0
                        
                        norm_val = val * scale
                        
                        # 2. Reasonableness Check (Sanity Guard)
                        # If Assets/Liabilities/Cash > 1000 Trillion (10^15), it's likely a unit error
                        # CMB 2015 Assets is ~5 Trillion. If we get 500 Trillion, it's 100x wrong.
                        if is_large and metric_name in ["total_assets", "total_liabilities", "cash_and_equivalents", "total_loans", "total_debt"]:
                            if abs(norm_val) > 100_000_000_000_000: # 100 Trillion
                                self.log(f"  [Sanity Guard] Value {norm_val} too large for metric '{metric_name}'. Forcing scale correction (10^8 -> 10^6).")
                                scale = scale / 100.0 if scale >= 100_000_000 else scale
                                norm_val = val * scale

                        # Include position info: (value, scale, distance, keyword_pos, value_pos)
                        dist = raw_start 
                        all_candidates.append((norm_val, scale, dist, start_pos, value_pos))
                    except Exception as e: 
                        self.log(f"  Candidate error: {e}")
                        continue
        return all_candidates

if __name__ == "__main__":
    # Test stub
    pass
