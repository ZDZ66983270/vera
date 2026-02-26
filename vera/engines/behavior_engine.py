import yaml
import os
from typing import Dict, Any, List, Optional

class BehaviorEngine:
    """
    BehaviorEngine: 统一输出资产姿态与行为建议。
    基于行为决策规则表 (behavior_rules.yaml) 生成标准化的 POSTURE。
    """
    
    def __init__(self, rules_path: Optional[str] = None):
        if rules_path is None:
            # Default path relative to project root
            rules_path = os.path.join(os.path.dirname(__file__), "../../config/behavior_rules.yaml")
        
        try:
            with open(rules_path, "r", encoding="utf-8") as f:
                self.rules = yaml.safe_load(f)
        except Exception as e:
            print(f"Error loading behavior rules: {e}")
            self.rules = {"priority_order": [], "fallback": {"posture": "HOLD", "reason": "规则库加载失败"}}

    def decide(
        self,
        risk: Dict[str, Any],         # risk_overlay node
        valuation: Dict[str, Any],    # valuation node
        quality: Dict[str, Any],      # quality_buffer node
        unlock_flags: Optional[Dict[str, Any]] = None,
        csp_strategy: Optional[Dict[str, Any]] = None,
        csp_contract: Optional[Dict[str, Any]] = None,
        price_structure_code: str = "US_TREND_DOWN" # New input from narrative logic
    ) -> Dict[str, Any]:
        """
        统一决策入口，返回包含 posture, suggestion, cognitive_warning 的字典。
        """
        ctx = self._build_context(risk, valuation, quality, price_structure_code)
        
        # 匹配优先级规则
        for rule in self.rules.get("priority_order", []):
            if self._match_rule(rule.get("when", {}), ctx):
                posture = rule["posture"]
                return {
                    "posture": posture,
                    "suggestion": self._build_suggestion(posture, ctx),
                    "cognitive_warning": self._build_warning(posture, ctx),
                    "matched_rule": rule["name"],
                    "risk_score": 0 # Legacy compatibility
                }

        # Fallback
        fb = self.rules.get("fallback", {"posture": "HOLD", "reason": "未命中规则"})
        posture = fb["posture"]
        return {
            "posture": posture,
            "suggestion": self._build_suggestion(posture, ctx),
            "cognitive_warning": fb.get("reason", "保持观测。"),
            "matched_rule": "fallback",
            "risk_score": 0
        }

    def _build_context(self, risk: Dict[str, Any], valuation: Dict[str, Any], quality: Dict[str, Any], ps_code: str) -> Dict[str, Any]:
        # Extract valuation percentile
        vp = valuation.get("valuation_percentile") or valuation.get("pe_percentile") or 50.0
        if isinstance(vp, (int, float)) and vp <= 1.0:
            vp *= 100
            
        # Extract quality grade
        qg = quality.get("grade") or quality.get("quality_buffer_level") or "MEDIUM"
        
        # Extract R_state (Short window)
        rs = risk.get("R_state") or risk.get("recent_cycle", {}).get("state") or "UNKNOWN"
        
        return {
            "valuation_percentile": vp,
            "quality_grade": qg,
            "short_window_r_state": rs,
            "price_structure": ps_code,
        }

    def _match_rule(self, cond: Dict[str, Any], ctx: Dict[str, Any]) -> bool:
        vp = ctx["valuation_percentile"]
        qg = ctx["quality_grade"]
        rs = ctx["short_window_r_state"]
        ps = ctx["price_structure"]

        # 估值分位条件
        if "valuation_percentile_min" in cond and vp < cond["valuation_percentile_min"]:
            return False
        if "valuation_percentile_max" in cond and vp >= cond["valuation_percentile_max"]:
            return False

        # 质量
        if "quality_grade_in" in cond and qg not in cond["quality_grade_in"]:
            return False

        # 短窗 R-state
        if "short_window_r_state_in" in cond and rs not in cond["short_window_r_state_in"]:
            return False
        if "short_window_r_state_not_in" in cond and rs in cond["short_window_r_state_not_in"]:
            return False

        # 价格结构
        if "price_structure_in" in cond and ps not in cond["price_structure_in"]:
            return False

        return True

    def _build_suggestion(self, posture: str, ctx: Dict[str, Any]) -> str:
        if posture == "EXIT":
            return "风险与估值都处于高位，建议尽快回避风险，逐步退出仓位。"
        if posture == "REDUCE":
            return "风险与估值偏高，建议以减仓和防守为主，避免大幅加仓或杠杆。"
        if posture == "ADD":
            return "估值偏低且质量尚可，在控制仓位与分散前提下，可择机逐步加仓。"
        # HOLD
        return "估值与风险大体均衡，建议保持现有仓位，重点跟踪后续信号变化。"

    def _build_warning(self, posture: str, ctx: Dict[str, Any]) -> str:
        if posture in ("EXIT", "REDUCE"):
            return "短期仍存在较大波动与回撤风险，操作上以防守与风险控制为先。"
        if posture == "ADD":
            return "尽管当前性价比较高，仍需注意单一资产集中度和宏观环境变化。"
        return "当前不建议激进行动，耐心观察价格与基本面的进一步演化。"

# Forward compatibility
def decide_behavior(risk, valuation, quality, **kwargs):
    return BehaviorEngine().decide(risk, valuation, quality, **kwargs)
