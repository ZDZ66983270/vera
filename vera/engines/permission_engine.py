# vera/engines/permission_engine.py

class PermissionEngine:
    """
    融合 U_state + O_state
    输出最终 R_state + 动作许可
    """

    def evaluate(self, U_state: str, O_state: str) -> dict:
        # 一票否决权 (U3 is always RED)
        if U_state == "U3_DISCOVERY":
            return self._red_state("Price discovery phase (U3)")

        if U_state == "U4_STABILIZATION":
            return self._yellow_state("Stabilization phase (U4)")

        # Green Light Conditions
        # Reversal OR Range, combined with IV Crush (Efficiency Window)
        if U_state in ["U5_REVERSAL", "U2_RANGE"] and O_state == "O3_IV_CRUSH":
            return self._green_state(f"{U_state} with IV Crush")

        # Default to YELLOW (Transition or Mixed signals)
        return self._yellow_state(f"Transition state ({U_state} + {O_state})")

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
