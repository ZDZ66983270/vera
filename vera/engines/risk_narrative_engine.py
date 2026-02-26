from typing import Dict, Any, List
from core.config_loader import load_yaml_config

class RiskNarrativeEngine:
    """
    风险叙事引擎 (A4)
    基于 D-State、MaxDD 和估值等指标生成结构化、人性化的风险解读文字。
    """
    
    def __init__(self):
        self.rules = load_yaml_config("config/risk_narrative_rules.yaml")

    def build(self, analysis_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        生成风险叙事
        """
        if not self.rules:
            return {"text": "规则文件缺失，无法生成风险解读。", "tags": []}

        risk = analysis_result.get("risk_overlay", {})
        val = analysis_result.get("valuation", {})
        
        d_state = risk.get("D_state", "UNKNOWN")
        mdd_1y = abs(risk.get("one_year_max_dd", 0.0))
        val_pct = val.get("valuation_percentile", 50.0)
        
        # 1. 长周期解读
        long_text = self.rules["long_horizon"]["states"].get("DEFAULT", {}).get("text", "")
        for key, state in self.rules["long_horizon"]["states"].items():
            if key == "DEFAULT": continue
            if d_state in state.get("when", {}).get("d_states", []):
                long_text = state["text"]
                break
        
        # 2. 短周期解读
        short_text = "短期走势平稳。"
        if mdd_1y > 0.15:
            short_text = self.rules["short_window"]["regimes"]["CRASH"]["text"]
        elif mdd_1y > 0.05:
            short_text = self.rules["short_window"]["regimes"]["CORRECTION"]["text"]
        else:
            short_text = self.rules["short_window"]["regimes"]["SIDEWAYS"]["text"]
            
        # 3. 估值叠层
        val_key = "NEUTRAL"
        if val_pct <= 25: val_key = "CHEAP"
        elif val_pct >= 75: val_key = "EXPENSIVE"
        val_text = self.rules["valuation_overlay"].get(val_key, "")

        # 4. 组合模板
        tmpl = self.rules["templates"]["default"]
        full_text = f"{tmpl['intro']}\n\n"
        full_text += f"**长周期视角**：{long_text}\n"
        full_text += f"**短窗现状**：{short_text}\n"
        full_text += f"**估值对冲**：{val_text}\n\n"
        full_text += tmpl["outro"]
        
        # 5. 生成标签 (基于简单逻辑)
        tags = []
        if d_state in ["D3", "D5"]: tags.append("STRUCTURAL_BREAK")
        if mdd_1y > 0.10: tags.append("HIGH_VOLATILITY")
        if val_pct <= 15: tags.append("DEEP_VALUE")
        
        return {
            "text": full_text,
            "tags": tags
        }
