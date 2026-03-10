#!/usr/bin/env python3
"""
test_balance_shipping.py

完整测试 - 验证发货均衡性

功能：
1. 连续运行 15 天
2. 统计每日发货量
3. 计算均衡性指标
4. 生成详细报告

使用方式：
    python3 test_balance_shipping.py
"""

import sys
import json
import random
from pathlib import Path
from datetime import datetime
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent))

from rolling_optimizer import RollingOptimizer
from state_manager import StateManager
import shutil


def reset_state():
    """重置状态并创建合同缓存"""
    state_dir = Path("./state")
    if state_dir.exists():
        shutil.rmtree(state_dir)
    state_dir.mkdir(exist_ok=True)
    
    # 创建合同缓存
    contracts_cache = [
        {
            "cid": "HT-2026-001",
            "receiver": "R1",
            "Q": 520.0,
            "start_day": 60,
            "end_day": 79,
            "products": [{"product_name": "A", "unit_price": 800.0}, {"product_name": "B", "unit_price": 1200.0}],
        },
        {
            "cid": "HT-2026-002",
            "receiver": "R2",
            "Q": 900.0,
            "start_day": 64,
            "end_day": 84,
            "products": [{"product_name": "A", "unit_price": 800.0}, {"product_name": "B", "unit_price": 1200.0}],
        },
    ]
    
    cache_file = state_dir / "contracts_cache.json"
    with open(cache_file, 'w', encoding='utf-8') as f:
        json.dump(contracts_cache, f, indent=2, ensure_ascii=False)
    
    print("状态已重置，合同缓存已创建\n")


def initialize_first_state(today=10):
    """初始化首日状态"""
    state_mgr = StateManager("./state")
    
    delivered_so_far = {
        "HT-2026-001": 0.0,
        "HT-2026-002": 0.0,
    }
    
    in_transit_orders = [
        {
            "order_id": "DL001",
            "cid": "HT-2026-001",
            "warehouse": "W1",
            "category": "A",
            "ship_day": today - 1,
            "weight": 35.0,
            "status": "pending",
        },
        {
            "order_id": "DL002",
            "cid": "HT-2026-002",
            "warehouse": "W1",
            "category": "A",
            "ship_day": today - 1,
            "weight": 36.0,
            "status": "pending",
        },
    ]
    
    state_mgr.update_state(
        delivered_so_far=delivered_so_far,
        in_transit_orders=in_transit_orders,
        x_prev={},
        today=today - 1,
    )
    
    print(f"状态已初始化（today={today}）\n")


def run_balance_test(start_day=10, num_days=15):
    """
    运行均衡性测试
    
    参数:
        start_day: 起始日
        num_days: 运行天数
    """
    print("=" * 80)
    print("PreModels v2 发货均衡性完整测试")
    print(f"起始日：Day {start_day}")
    print(f"运行天数：{num_days} 天")
    print("=" * 80)
    
    # 重置状态
    reset_state()
    
    # 初始化首日状态
    initialize_first_state(start_day)
    
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
        today = start_day + day_offset
        
        try:
            # 运行优化
            result = optimizer.run(today=today, H=10)
            
            # 统计今日计划
            shipments = result.get('x_today', {})
            total_tons = sum(shipments.values())
            total_trucks = sum(result.get('trucks', {}).values())
            
            # 记录结果
            daily_data = {
                'day': today,
                'total_tons': total_tons,
                'total_trucks': total_trucks,
                'shipments': [],
            }
            
            # 记录每条发货明细
            for key, tons in sorted(shipments.items()):
                parts = key.split('_')
                if len(parts) == 4:
                    warehouse, cid, category, day = parts
                    daily_data['shipments'].append({
                        'warehouse': warehouse,
                        'cid': cid,
                        'category': category,
                        'tons': tons,
                    })
                    contract_progress[cid] += tons
            
            daily_results.append(daily_data)
            daily_totals.append(total_tons)
            
            # 打印进度
            print(f"Day {today:2d}: {total_tons:6.2f} 吨 ({len(shipments)}条)  "
                  f"累计：HT-2026-001={contract_progress['HT-2026-001']:6.1f}吨  "
                  f"HT-2026-002={contract_progress['HT-2026-002']:6.1f}吨")
            
        except Exception as e:
            print(f"Day {today:2d}: 运行失败 - {e}")
            break
    
    # 生成均衡性分析报告
    print("\n" + "=" * 80)
    print("发货均衡性分析报告")
    print("=" * 80)
    
    if not daily_totals:
        print("无数据")
        return
    
    # 计算统计指标
    avg_daily = sum(daily_totals) / len(daily_totals)
    max_daily = max(daily_totals)
    min_daily = min(daily_totals)
    std_dev = (sum((x - avg_daily) ** 2 for x in daily_totals) / len(daily_totals)) ** 0.5
    cv = (std_dev / avg_daily) * 100  # 变异系数
    
    print(f"\n【统计指标】")
    print(f"  运行天数：{len(daily_totals)} 天")
    print(f"  总发货量：{sum(daily_totals):.2f} 吨")
    print(f"  日均发货：{avg_daily:.2f} 吨/天")
    print(f"  最大日发货：{max_daily:.2f} 吨")
    print(f"  最小日发货：{min_daily:.2f} 吨")
    print(f"  极差：{max_daily - min_daily:.2f} 吨")
    print(f"  标准差：{std_dev:.2f}")
    print(f"  变异系数 (CV): {cv:.1f}%")
    
    # 均衡性评价
    print(f"\n【均衡性评价】")
    if cv < 10:
        print(f"  评价：优秀 (CV={cv:.1f}% < 10%)")
        print(f"  说明：发货非常均衡")
    elif cv < 20:
        print(f"  评价：良好 (CV={cv:.1f}% 在 10-20% 之间)")
        print(f"  说明：发货较为均衡")
    elif cv < 30:
        print(f"  评价：一般 (CV={cv:.1f}% 在 20-30% 之间)")
        print(f"  说明：发货均衡性一般")
    else:
        print(f"  评价：需改进 (CV={cv:.1f}% > 30%)")
        print(f"  说明：发货波动较大")
    
    # 每日发货可视化
    print(f"\n【每日发货趋势图】")
    max_bar_width = 50
    scale = max_daily / max_bar_width
    
    print(f"{'日期':<8} {'吨数':>10} {'可视化':<50}")
    print("-" * 80)
    
    for i, total in enumerate(daily_totals):
        bar_width = int(total / scale)
        bar = '█' * bar_width
        day_num = start_day + i
        print(f"Day {day_num:<5} {total:>10.2f} {bar}")
    
    # 合同完成进度
    print(f"\n【合同完成进度】")
    contracts_info = {
        "HT-2026-001": {"total": 520.0, "receiver": "R1"},
        "HT-2026-002": {"total": 900.0, "receiver": "R2"},
    }
    
    for cid, info in contracts_info.items():
        completed = contract_progress[cid]
        total = info['total']
        receiver = info['receiver']
        progress = (completed / total) * 100
        bar_width = int(progress / 2)
        bar = '█' * bar_width + '░' * (50 - bar_width)
        
        print(f"  {cid} (收货方：{receiver}):")
        print(f"    合同总量：{total} 吨")
        print(f"    已完成：{completed:.2f} 吨 ({progress:.1f}%)")
        print(f"    {bar}")
    
    # 仓库发货分布
    print(f"\n【仓库发货分布】")
    warehouse_totals = defaultdict(float)
    for day_data in daily_results:
        for shipment in day_data['shipments']:
            warehouse_totals[shipment['warehouse']] += shipment['tons']
    
    total_all = sum(warehouse_totals.values())
    for wh, total in sorted(warehouse_totals.items()):
        pct = (total / total_all) * 100
        bar_width = int(pct / 2)
        bar = '█' * bar_width + '░' * (50 - bar_width)
        print(f"  {wh}: {total:7.2f} 吨 ({pct:5.1f}%) {bar}")
    
    # 品类发货分布
    print(f"\n【品类发货分布】")
    category_totals = defaultdict(float)
    for day_data in daily_results:
        for shipment in day_data['shipments']:
            category_totals[shipment['category']] += shipment['tons']
    
    for cat, total in sorted(category_totals.items()):
        pct = (total / total_all) * 100
        bar_width = int(pct / 2)
        bar = '█' * bar_width + '░' * (50 - bar_width)
        print(f"  品类 {cat}: {total:7.2f} 吨 ({pct:5.1f}%) {bar}")
    
    # 保存详细数据
    summary_file = Path("./state/balance_test_summary.json")
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump({
            'test_date': datetime.now().isoformat(),
            'start_day': start_day,
            'num_days': num_days,
            'statistics': {
                'total_tons': sum(daily_totals),
                'avg_daily': avg_daily,
                'max_daily': max_daily,
                'min_daily': min_daily,
                'range': max_daily - min_daily,
                'std_dev': std_dev,
                'cv': cv,
            },
            'daily_totals': daily_totals,
            'contract_progress': dict(contract_progress),
            'warehouse_totals': dict(warehouse_totals),
            'category_totals': dict(category_totals),
        }, f, indent=2, ensure_ascii=False, default=str)
    
    print(f"\n【报告保存】")
    print(f"  详细数据：{summary_file}")
    
    print("\n" + "=" * 80)
    print("测试完成")
    print("=" * 80)


if __name__ == "__main__":
    run_balance_test(start_day=10, num_days=15)
