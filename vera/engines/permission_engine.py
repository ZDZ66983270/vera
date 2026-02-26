# vera/engines/permission_engine.py

class PermissionEngine:
    """
    融合 U_state + O_state
    输出最终 R_state + 动作许可
    """

    def evaluate(self, risk: dict, valuation: dict, quality: dict) -> dict:
        """
        策略层许可评估 (A2.1)
        """
        d_state = risk.get("D_state", "UNKNOWN")
        val_pct = valuation.get("valuation_percentile", 50.0)
        qual_grade = quality.get("grade", "MEDIUM")

        # 示例逻辑：如果处于极端风险 D3/D5，强制 RED
        if d_state in ["D3", "D5"]:
            return self._red_state(f"Market Discovery/Collapse ({d_state})")

        # 如果估值适中且处于安全区 D0/D4，绿色
        if d_state in ["D0", "D4"] and val_pct < 60:
            return self._green_state(f"Safe structural zone ({d_state}) with fair valuation")

        # 其他情况黄色
        return self._yellow_state(f"Wait and see ({d_state})")

    def _red_state(self, reason):
        return {
            "R_state": "RED",
            "summary_label_zh": "禁止操作",
            "summary_note_zh": "处于价格发现期且波动率极高，建议观望，不开任何新仓。",
            "allowed_actions": {
                "buy_underlying": False,
                "sell_put_csp": False,
                "roll_put": False
            },
            "reason": reason
        }

    def _yellow_state(self, reason):
        return {
            "R_state": "YELLOW",
            "summary_label_zh": "谨慎观察",
            "summary_note_zh": "市场结构尚未确立，抛压虽衰竭但动能不足，建议保持轻仓或观望。",
            "allowed_actions": {
                "buy_underlying": False,
                "sell_put_csp": False,
                "roll_put": False
            },
            "constraints": {
                 "note": "Observation only. Strict risk control."
            },
            "reason": reason
        }

    def _green_state(self, reason):
        return {
            "R_state": "GREEN",
            "summary_label_zh": "参与交易",
            "summary_note_zh": "反转确认且波动率收敛，属于高效参与窗口，可按策略建仓。",
            "allowed_actions": {
                "buy_underlying": True,
                "sell_put_csp": True,
                "roll_put": True
            },
            "constraints": {
                "min_dte": 60,
                "note": "Apply strategy-specific debit/strike rules"
            },
            "reason": reason
        }
