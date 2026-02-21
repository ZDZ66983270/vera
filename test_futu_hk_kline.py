#!/usr/bin/env python3
"""
测试脚本：获取港股历史K线数据
使用 Futu OpenAPI 获取 09988.HK (阿里巴巴) 和 00005.HK (汇丰控股) 的历史K线数据
重点监控PE比率的返回情况
"""

import futu as ft
from datetime import datetime, timedelta
import pandas as pd


def fetch_hk_stock_kline(stock_code, start_date, end_date, ktype=ft.KLType.K_DAY):
    """
    获取港股历史K线数据
    
    Args:
        stock_code: 股票代码，如 '09988' 或 '00005'
        start_date: 开始日期，格式 'yyyy-MM-dd'
        end_date: 结束日期，格式 'yyyy-MM-dd'
        ktype: K线类型，默认日K线
    
    Returns:
        DataFrame: K线数据，包含PE等字段
    """
    # 创建行情上下文
    quote_ctx = ft.OpenQuoteContext(host='127.0.0.1', port=11111)
    
    try:
        # 构建港股代码
        hk_code = f'HK.{stock_code}'
        
        print(f"\n{'='*60}")
        print(f"正在获取 {hk_code} 的历史K线数据...")
        print(f"时间范围: {start_date} 至 {end_date}")
        print(f"{'='*60}\n")
        
        # 请求历史K线数据
        ret, data, page_req_key = quote_ctx.request_history_kline(
            code=hk_code,
            start=start_date,
            end=end_date,
            ktype=ktype,
            autype=ft.AuType.QFQ,  # 前复权
            fields=[
                ft.KLField.ALL  # 获取所有字段，包括PE
            ],
            max_count=1000,  # 最多返回1000条
            extended_time=False
        )
        
        if ret == ft.RET_OK:
            print(f"✓ 成功获取 {len(data)} 条K线数据\n")
            
            # 显示数据基本信息
            print(f"数据列: {list(data.columns)}\n")
            
            # 检查PE字段是否存在
            if 'pe_ratio' in data.columns:
                print("✓ PE比率字段存在")
                pe_stats = data['pe_ratio'].describe()
                print(f"\nPE比率统计信息:")
                print(pe_stats)
                
                # 显示PE非零的数据条数
                non_zero_pe = data[data['pe_ratio'] > 0]
                print(f"\nPE > 0 的数据条数: {len(non_zero_pe)} / {len(data)}")
                print(f"PE = 0 的数据条数: {len(data[data['pe_ratio'] == 0])}")
                
                # 显示最近10条数据的PE情况
                print(f"\n最近10条数据的PE情况:")
                print(data[['time_key', 'code', 'close', 'pe_ratio', 'turnover_rate']].tail(10))
                
            else:
                print("✗ 警告: PE比率字段不存在于返回数据中")
                print(f"可用字段: {list(data.columns)}")
            
            return data
            
        else:
            print(f"✗ 获取K线数据失败: {data}")
            return None
            
    except Exception as e:
        print(f"✗ 发生错误: {str(e)}")
        import traceback
        traceback.print_exc()
        return None
        
    finally:
        # 关闭连接
        quote_ctx.close()


def analyze_pe_data(stock_code, data):
    """
    分析PE数据的详细情况
    
    Args:
        stock_code: 股票代码
        data: K线数据DataFrame
    """
    if data is None or data.empty:
        print(f"\n{stock_code}: 无数据可分析")
        return
    
    print(f"\n{'='*60}")
    print(f"{stock_code} PE数据详细分析")
    print(f"{'='*60}\n")
    
    if 'pe_ratio' not in data.columns:
        print("PE字段不存在，无法分析")
        return
    
    # 1. PE值的分布情况
    print("1. PE值分布:")
    pe_zero = len(data[data['pe_ratio'] == 0])
    pe_positive = len(data[data['pe_ratio'] > 0])
    pe_negative = len(data[data['pe_ratio'] < 0])
    
    print(f"   PE = 0:  {pe_zero:4d} 条 ({pe_zero/len(data)*100:.1f}%)")
    print(f"   PE > 0:  {pe_positive:4d} 条 ({pe_positive/len(data)*100:.1f}%)")
    print(f"   PE < 0:  {pe_negative:4d} 条 ({pe_negative/len(data)*100:.1f}%)")
    
    # 2. PE有效数据的统计
    valid_pe = data[data['pe_ratio'] > 0]['pe_ratio']
    if len(valid_pe) > 0:
        print(f"\n2. 有效PE数据统计 (PE > 0):")
        print(f"   最小值: {valid_pe.min():.2f}")
        print(f"   最大值: {valid_pe.max():.2f}")
        print(f"   平均值: {valid_pe.mean():.2f}")
        print(f"   中位数: {valid_pe.median():.2f}")
        
        # 3. 显示PE变化趋势（最近30天）
        recent_data = data.tail(30)
        if len(recent_data) > 0:
            print(f"\n3. 最近30天PE趋势:")
            print(recent_data[['time_key', 'close', 'pe_ratio']].to_string(index=False))
    else:
        print("\n✗ 警告: 没有有效的PE数据 (所有PE值都 <= 0)")


def main():
    """主函数"""
    print("="*60)
    print("港股历史K线数据获取测试")
    print("重点监控PE比率返回情况")
    print("="*60)
    
    # 设置测试参数
    stocks = ['09988', '00005']  # 阿里巴巴、汇丰控股
    
    # 设置时间范围：最近3个月
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
    
    print(f"\n测试股票: {', '.join(stocks)}")
    print(f"时间范围: {start_date} 至 {end_date}")
    print(f"\n注意: 请确保 FutuOpenD 已启动并监听在 127.0.0.1:11111\n")
    
    # 存储结果
    results = {}
    
    # 遍历股票获取数据
    for stock_code in stocks:
        data = fetch_hk_stock_kline(stock_code, start_date, end_date)
        results[stock_code] = data
        
        # 分析PE数据
        if data is not None:
            analyze_pe_data(stock_code, data)
    
    # 总结
    print(f"\n{'='*60}")
    print("测试总结")
    print(f"{'='*60}\n")
    
    for stock_code, data in results.items():
        if data is not None:
            pe_available = 'pe_ratio' in data.columns
            pe_valid_count = len(data[data['pe_ratio'] > 0]) if pe_available else 0
            print(f"{stock_code}: 获取 {len(data)} 条数据, "
                  f"PE字段{'存在' if pe_available else '不存在'}, "
                  f"有效PE数据 {pe_valid_count} 条")
        else:
            print(f"{stock_code}: 获取失败")
    
    print("\n测试完成!")


if __name__ == '__main__':
    main()
