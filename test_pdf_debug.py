#!/usr/bin/env python3
"""
测试脚本：直接运行 PDF 解析器，查看完整的 debug 输出
用于诊断为什么财报导入失败
"""

import sys
import os

# 添加项目路径
sys.path.insert(0, '/Users/zhangzy/My Docs/Privates/22-AI编程/VERA')

from utils.pdf_engine import PDFFinancialParser

def test_pdf_parser(pdf_path, asset_id="CN:STOCK:600036"):
    """测试 PDF 解析器"""
    print(f"=" * 80)
    print(f"测试文件: {pdf_path}")
    print(f"资产ID: {asset_id}")
    print(f"=" * 80)
    
    # 创建解析器
    parser = PDFFinancialParser(pdf_path=pdf_path, asset_id=asset_id)
    
    # 执行解析
    result = parser.parse_financials()
    
    # 打印调试日志
    print("\n" + "=" * 80)
    print("📋 调试日志 (Debug Logs)")
    print("=" * 80)
    
    debug_logs = result.get('debug_logs', [])
    if debug_logs:
        for i, log in enumerate(debug_logs, 1):
            print(f"{i}. {log}")
    else:
        print("⚠️ 没有调试日志！")
    
    # 打印提取结果
    print("\n" + "=" * 80)
    print("📊 提取结果")
    print("=" * 80)
    
    # 过滤掉 debug_logs 和 raw_text
    extracted = {k: v for k, v in result.items() 
                 if k not in ['debug_logs', 'raw_text'] and v is not None}
    
    if extracted:
        for key, value in extracted.items():
            print(f"  {key}: {value}")
    else:
        print("⚠️ 没有提取到任何数据！")
    
    # 打印原始文本长度
    print("\n" + "=" * 80)
    print("📄 原始文本信息")
    print("=" * 80)
    raw_text = result.get('raw_text', '')
    print(f"文本长度: {len(raw_text)} 字符")
    if raw_text:
        print(f"前500字符:\n{raw_text[:500]}")
    
    return result

if __name__ == "__main__":
    # 测试文件路径（请根据实际情况修改）
    test_file = "22年一季度.pdf"
    
    if not os.path.exists(test_file):
        print(f"❌ 文件不存在: {test_file}")
        print("请将 PDF 文件放在当前目录，或修改 test_file 变量指向正确的路径")
        sys.exit(1)
    
    result = test_pdf_parser(test_file)
