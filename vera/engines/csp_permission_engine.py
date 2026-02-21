from .permission_engine import PermissionEngine

class CSPPermissionEngine:
    """
    CSP 策略专用评估引擎，对接 dashboard 数据
    """
    
    @staticmethod
    def evaluate_from_dashboard(data) -> dict:
        """
        从 DashboardData 对象评估 CSP 策略权限和指标
        """
        # 1. 提取 U_state 和 O_state
        u_state = "U2_RANGE"
        if hasattr(data, 'underlying') and data.underlying:
             u_state = data.underlying.get('U_state', "U2_RANGE")
        elif hasattr(data, 'path') and data.path:
             # Fallback to D_state or similar if U_state not available
             u_state = data.path.get('state', "U2_RANGE")
             
        o_state = "O2_PLATEAU"
        if hasattr(data, 'options') and data.options:
             o_state = data.options.get('O_state', "O2_PLATEAU")
             
        # 2. 调用标准权限引擎
        pe = PermissionEngine()
        result = pe.evaluate(u_state, o_state)
        
        # 3. 补充 CSP 专用指标
        # 这里的 current_price 是审计合约时的基准
        current_price = getattr(data, 'price', 0.0)
        
        # 构造 metrics 字典
        metrics = {
            'current_price': current_price,
            'u_state': u_state,
            'o_state': o_state,
        }
        
        # 将 pe 的结果包装进返回对象
        return {
            'R_state': result['R_state'],
            'metrics': metrics,
            'allowed_actions': result['allowed_actions'],
            'reason': result.get('reason', '')
        }
