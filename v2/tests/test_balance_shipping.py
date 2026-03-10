#!/usr/bin/env python3
"""
test_balance_shipping.py

发货均衡性测试

功能：
1. 连续多日运行优化
2. 统计每日发货量
3. 分析均衡性指标
4. 生成均衡性报告

使用方式：
    python3 test_balance_shipping.py --start-date 2026-03-10 --days 10
"""

import sys
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from models.rolling_optimizer import RollingOptimizer
from core.state_manager import StateManager
from core.date_utils import DateUtils


def reset_state():
    """重置状态并创建合同缓存"""
    state_dir = Path("./state")
    if state_dir.exists():
        for f in state_dir.glob("*.json"):
            f.unlink()
    else:
        state_dir.mkdir(exist_ok=True)
    
    # 创建合同缓存（使用日期字符串）
    contracts_cache = [
        {
            "cid": "HT-2026-001",
            "receiver": "R1",
            "Q": 520.0,
            "start_day": "2026-03-01",
            "end_day": "2026-03-20",
            "products": [
                {"product_name": "A", "unit_price": 800.0},
                {"product_name": "B", "unit_price": 1200.0},
            ],
        },
        {
            "cid": "HT-2026-002",
            "receiver": "R2",
            "Q": 900.0,
            "start_day": "2026-03-05",
            "end_day": "2026-03-25",
            "products": [
                {"product_name": "A", "unit_price": 800.0},
                {"product_name": "B", "unit_price": 1200.0},
            ],
        },
    ]
    
    cache_file = state_dir / "contracts_cache.json"
    with open(cache_file, 'w', encoding='utf-8') as f:
        json.dump(contracts_cache, f, indent=2, ensure_ascii=False)
    
    print("状态已重置，合同缓存已创建\n")


def initialize_first_state(today_date="2026-03-10"):
    """初始化首日状态"""
    state_mgr = StateManager("./state")
    
    delivered_so_far = {
        "HT-2026-001": 0.0,
        "HT-2026-002": 0.0,
    }
    
    yesterday = DateUtils.add_days(today_date, -1)
    in_transit_orders = [
        {
            "order_id": "DL001",
            "cid": "HT-2026-001",
            "warehouse": "W1",
            "category": "A",
            "ship_day": yesterday,
            "weight": 35.0,
            "status": "pending",
        },
        {
            "order_id": "DL002",
            "cid": "HT-2026-002",
            "warehouse": "W1",
            "category": "A",
            "ship_day": yesterday,
            "weight": 36.0,
            "status": "pending",
        },
    ]
    
    state_mgr.update_state(
        delivered_so_far=delivered_so_far,
        in_transit_orders=in_transit_orders,
        x_prev={},
        today=today_date,
    )
    
    print(f"状态已初始化（date={today_date}）\n")


def run_balance_test(start_date="2026-03-10", num_days=10):
    """
    运行均衡性测试
    
    参数:
        start_date: 起始日期
        num_days: 运行天数
    """
    print("=" * 80)
    print("PreModels v2 发货均衡性完整测试")
    print(f"起始日期：{start_date}")
    print(f"运行天数：{num_days} 天")
    print("=" * 80)
    
    # 重置状态
    reset_state()
    
    # 初始化首日状态
    initialize_first_state(start_date)
    
    # 初始化优化器
    optimizer = RollingOptimizer(
        state_dir="./state",
        api_base_url="http://127.0.0.1:8007",
    )
    
    # 每日运行记录
    daily_results = []
    contract_progress = defaultdict(float)
    daily_totals = []
    
    for day_offset in range(num_days):
        today = DateUtils.add_days(start_date, day_offset)
        
        try:
            # 运行优化
            result = optimizer.run(today_date=today, H=5)
            
            # 统计今日计划
            shipments = result.get('x_today', {})
            total_tons = sum(shipments.values()) if shipments else 0.0
            total_trucks = sum(result.get('trucks', {}).values()) if result.get('trucks') else 0
            
            # 记录结果
            daily_data = {
                'date': today,
                'total_tons': total_tons,
                'total_trucks': total_trucks,
                'shipments': [],
            }
            
            # 记录每条发货明细
            for key, tons in sorted(shipments.items()):
                parts = key.split('_')
                if len(parts) >= 4:
                    warehouse = parts[0]
                    cid = parts[1]
                    category = parts[2]
                    daily_data['shipments'].append({
                        'warehouse': warehouse,
                        'cid': cid,
                        'category': category,
                        'tons': tons,
                    })
                    contract_progress[cid] += tons
            
            daily_results.append(daily_data)
            daily_totals.append(total_tons)
            
            print(f"Day {day_offset + 1} ({today}): {total_tons:.2f} 吨, {total_trucks} 车")
            
        except Exception as e:
            print(f"Day {day_offset + 1} ({today}): 运行失败 - {e}")
            daily_results.append({
                'date': today,
                'total_tons': 0,
                'total_trucks': 0,
                'error': str(e),
            })
            daily_totals.append(0)
    
    # 生成均衡性报告
    generate_report(daily_results, daily_totals, contract_progress)
    
    return daily_results


def generate_report(daily_results, daily_totals, contract_progress):
    """
    生成均衡性报告
    
    参数:
        daily_results: 每日结果
        daily_totals: 每日总吨数
        contract_progress: 合同进度
    """
    print("\n" + "=" * 80)
    print("发货均衡性分析报告")
    print("=" * 80)
    
    # 过滤有效数据
    valid_totals = [t for t in daily_totals if t > 0]
    
    if not valid_totals:
        print("无数据")
        return
    
    # 计算统计指标
    avg_daily = sum(valid_totals) / len(valid_totals)
    max_daily = max(valid_totals)
    min_daily = min(valid_totals)
    std_dev = (sum((x - avg_daily) ** 2 for x in valid_totals) / len(valid_totals)) ** 0.5
    cv = std_dev / avg_daily if avg_daily > 0 else 0  # 变异系数
    
    print(f"\n统计指标:")
    print(f"  平均日发货：{avg_daily:.2f} 吨")
    print(f"  最大日发货：{max_daily:.2f} 吨")
    print(f"  最小日发货：{min_daily:.2f} 吨")
    print(f"  标准差：{std_dev:.2f}")
    print(f"  变异系数 (CV): {cv:.2%}")
    print(f"\n均衡性评价:", end=" ")
    if cv < 0.1:
        print("优秀 (CV < 10%)")
    elif cv < 0.2:
        print("良好 (CV < 20%)")
    elif cv < 0.3:
        print("一般 (CV < 30%)")
    else:
        print("较差 (CV >= 30%)")
    
    # 合同完成情况
    print(f"\n合同累计完成:")
    for cid, total in sorted(contract_progress.items()):
        print(f"  {cid}: {total:.2f} 吨")
    
    # 保存报告
    report_file = Path("./state/balance_report.json")
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump({
            'test_date': datetime.now().isoformat(),
            'statistics': {
                'avg_daily': avg_daily,
                'max_daily': max_daily,
                'min_daily': min_daily,
                'std_dev': std_dev,
                'cv': cv,
            },
            'daily_results': daily_results,
            'contract_progress': dict(contract_progress),
        }, f, indent=2, ensure_ascii=False, default=str)
    
    print(f"\n报告已保存：{report_file}")


def main():
    """主函数"""
    import argparse
    parser = argparse.ArgumentParser(description="发货均衡性测试")
    parser.add_argument("--start-date", type=str, default="2026-03-10", help="起始日期")
    parser.add_argument("--days", type=int, default=10, help="运行天数")
    args = parser.parse_args()
    
    run_balance_test(start_date=args.start_date, num_days=args.days)


if __name__ == "__main__":
    main()
