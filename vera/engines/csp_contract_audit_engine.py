from typing import Dict, Any, List, Optional
from core.config_loader import load_yaml_config

class CSPContractAuditEngine:
    """
    CSP 合约审计引擎 (A2.2)
    负责针对特定期权合约，结合资产上下文（估值、质量）进行合规性深度审计。
    """
    
    def __init__(self):
        self.rules = load_yaml_config("config/csp_contract_rules.yaml")
        if not self.rules:
            # Fallback inline defaults if file not found
            self.rules = {
                "global_defaults": {
                    "tenor_days": {"min": 15, "max": 90},
                    "delta": {"min": -0.35, "max": -0.10},
                    "moneyness": {"min_discount_pct": 0.05},
                    "yield_metrics": {"min_annual_yield": 0.08}
                },
                "pass_thresholds": {"min_score_pass": 60}
            }

    def audit(self, option: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        审计单个合约
        option: {strike, spot, dte, delta, iv, yield, discount, ...}
        context: {valuation_percentile, quality_grade}
        """
        reasons = []
        score = 100.0
        
        # 1. 获取规则 (考虑上下文调整)
        rules = self.rules["global_defaults"]
        val_pct = context.get("valuation_percentile", 50.0)
        qual_grade = context.get("quality_grade", "MEDIUM")
        
        # 应用估值调整
        for adj in self.rules.get("valuation_adjustments", []):
            wr = adj.get("when_valuation_pctile", [])
            if wr and wr[0] <= val_pct <= wr[1]:
                rules.update(adj.get("adjust", {}))
                
        # 应用质量调整
        for adj in self.rules.get("quality_adjustments", []):
            if adj.get("when_quality_grade") == qual_grade:
                rules.update(adj.get("adjust", {}))

        # 2. 执行审计逻辑
        
        # A. DTE 校验
        dte = option.get("dte", 0)
        if dte < rules.get("tenor_days", {}).get("min", 15) or dte > rules.get("tenor_days", {}).get("max", 90):
            score -= 20
            reasons.append({"code": "DTE_OUT_OF_RANGE", "message": self.rules["fail_reason_messages"]["DTE_OUT_OF_RANGE"]})

        # B. Delta 校验
        delta = option.get("delta", 0.0)
        if not (rules.get("delta", {}).get("min", -0.35) <= delta <= rules.get("delta", {}).get("max", -0.10)):
            score -= 25
            reasons.append({"code": "DELTA_OUT_OF_RANGE", "message": self.rules["fail_reason_messages"]["DELTA_OUT_OF_RANGE"]})

        # C. Discount 校验
        discount = option.get("discount", 0.0)
        min_disc = rules.get("moneyness", {}).get("min_discount_pct", 0.05)
        if discount < min_disc:
            score -= 40
            reasons.append({"code": "STRIKE_TOO_CLOSE", "message": self.rules["fail_reason_messages"]["STRIKE_TOO_CLOSE"]})

        # D. Yield 校验
        ann_yield = option.get("yield", 0.0)
        min_yield = rules.get("yield_metrics", {}).get("min_annual_yield", 0.08)
        if ann_yield < min_yield:
            score -= 30
            reasons.append({"code": "YIELD_TOO_LOW", "message": self.rules["fail_reason_messages"]["YIELD_TOO_LOW"]})

        # 3. 确定最终状态
        pass_line = rules.get("min_score_pass", self.rules["pass_thresholds"]["min_score_pass"])
        # 如果有核心风险不通过，强制 REJECTED
        status = "APPROVED" if score >= pass_line and discount >= min_disc else "REJECTED"
        
        suggestion = "当前合约各项指标均衡，符合交易标准。" if status == "APPROVED" else \
                     "当前合约风险收益比不佳或保护不足，建议重新筛选。"
        if not reasons and status == "REJECTED": # Should not happen with current logic but for safety
             suggestion = "得分较低，建议观望。"

        return {
            "contract_status": status,
            "contract_score": max(0.0, score),
            "reasons": reasons,
            "suggestion": suggestion,
        }
