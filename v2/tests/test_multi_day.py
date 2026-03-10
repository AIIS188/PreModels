#!/usr/bin/env python3
"""
test_multi_day.py

多日连续运行测试

功能：
1. 连续运行多日优化
2. 模拟每日磅单确认
3. 跟踪合同完成进度
4. 生成多日汇总报告

使用方式：
    python3 test_multi_day.py --days 5
"""

import sys
import json
import random
from pathlib import Path
from datetime import datetime

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
            "start_day": 60,  # 2026-03-01
            "end_day": 79,    # 2026-03-20
            "products": [{"product_name": "A", "unit_price": 800.0}, {"product_name": "B", "unit_price": 1200.0}],
        },
        {
            "cid": "HT-2026-002",
            "receiver": "R2",
            "Q": 900.0,
            "start_day": 64,  # 2026-03-05
            "end_day": 84,    # 2026-03-25
            "products": [{"product_name": "A", "unit_price": 800.0}, {"product_name": "B", "unit_price": 1200.0}],
        },
    ]
    
    cache_file = state_dir / "contracts_cache.json"
    with open(cache_file, 'w', encoding='utf-8') as f:
        json.dump(contracts_cache, f, indent=2, ensure_ascii=False)
    
    print("状态已重置，合同缓存已创建\n")


def simulate_weighbills(today, in_transit):
    """
    模拟磅单确认（简化版）
    
    假设：
    - 97% 的报单隔日到货
    - 3% 的报单当日到货
    """
    confirmed = []
    for order in in_transit:
        ship_day = order.get('ship_day', today - 1)
        delay = 1 if random.random() < 0.97 else 0
        arrival_day = ship_day + delay
        
        if arrival_day == today:
            confirmed.append({
                'order_id': order['order_id'],
                'cid': order['cid'],
                'warehouse': order['warehouse'],
                'category': order['category'],
                'weight': order['weight'],
                'arrival_day': today,
            })
    
    return confirmed


def initialize_first_state(today=10):
    """初始化首日状态"""
    from common_utils_v2 import Contract
    
    state_mgr = StateManager("./state")
    
    # 初始已到货量
    delivered_so_far = {
        "HT-2026-001": 0.0,
        "HT-2026-002": 0.0,
    }
    
    # 初始在途报单
    in_transit_orders = [
        {
            "order_id": "DL001",
            "cid": "HT-2026-001",
            "warehouse": "W1",
            "category": "A",
            "ship_day": today - 1,
            "weight": 35.0,
            "truck_id": "京 A12345",
            "driver_id": "张三",
            "status": "pending",
        },
        {
            "order_id": "DL002",
            "cid": "HT-2026-001",
            "warehouse": "W2",
            "category": "B",
            "ship_day": today - 1,
            "weight": 33.0,
            "truck_id": "京 B23456",
            "driver_id": "李四",
            "status": "pending",
        },
        {
            "order_id": "DL003",
            "cid": "HT-2026-002",
            "warehouse": "W1",
            "category": "A",
            "ship_day": today - 1,
            "weight": 36.0,
            "truck_id": "京 C34567",
            "driver_id": "王五",
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


def run_multi_day_test(start_day=10, num_days=5):
    """
    运行多日测试
    
    参数:
        start_day: 起始日
        num_days: 运行天数
    """
    print("=" * 80)
    print("PreModels v2 多日连续运行测试")
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
    contract_progress = {}
    
    for day_offset in range(num_days):
        today = start_day + day_offset
        
        print(f"\n{'=' * 80}")
        print(f"第 {day_offset + 1} 天：Day {today}")
        print(f"{'=' * 80}")
        
        try:
            # 运行优化
            print(f"\n运行优化...")
            result = optimizer.run(today=today, H=10)
            
            # 统计今日计划
            shipments = result.get('x_today', {})
            total_tons = sum(shipments.values())
            total_trucks = sum(result.get('trucks', {}).values())
            
            print(f"  今日计划：{len(shipments)} 条")
            print(f"  总吨数：{total_tons:.2f} 吨")
            print(f"  总车数：{total_trucks} 车")
            print(f"  平均载重：{total_tons/total_trucks:.1f} 吨/车" if total_trucks > 0 else "")
            
            # 打印详细计划
            print(f"\n  发货明细:")
            for key, tons in sorted(shipments.items()):
                parts = key.split('_')
                if len(parts) == 4:
                    warehouse, cid, category, day = parts
                    print(f"    {warehouse} -> {cid} ({category}): {tons:.2f} 吨")
            
            # 记录结果
            daily_results.append({
                'day': today,
                'shipments': len(shipments),
                'total_tons': total_tons,
                'total_trucks': total_trucks,
                'details': {k: v for k, v in shipments.items()}
            })
            
            # 更新合同进度
            for key, tons in shipments.items():
                parts = key.split('_')
                if len(parts) >= 2:
                    cid = parts[1]
                    contract_progress[cid] = contract_progress.get(cid, 0) + tons
            
            # 打印合同进度
            print(f"\n  合同累计完成:")
            for cid, total in sorted(contract_progress.items()):
                print(f"    {cid}: {total:.2f} 吨")
            
            # 模拟磅单确认（简化）
            # 实际应该从 PD API 获取
            
        except Exception as e:
            print(f"  运行失败：{e}")
            import traceback
            traceback.print_exc()
            break
    
    # 生成汇总报告
    print(f"\n{'=' * 80}")
    print("多日测试汇总报告")
    print(f"{'=' * 80}")
    
    total_tons_all = sum(r['total_tons'] for r in daily_results)
    total_trucks_all = sum(r['total_trucks'] for r in daily_results)
    avg_daily_tons = total_tons_all / len(daily_results) if daily_results else 0
    
    print(f"\n运行天数：{len(daily_results)}")
    print(f"总发货量：{total_tons_all:.2f} 吨")
    print(f"总车数：{total_trucks_all} 车")
    print(f"日均发货：{avg_daily_tons:.2f} 吨/天")
    print(f"平均载重：{total_tons_all/total_trucks_all:.1f} 吨/车" if total_trucks_all > 0 else "")
    
    print(f"\n每日发货统计:")
    print(f"{'日期':<8} {'计划数':>8} {'吨数':>12} {'车数':>8} {'平均载重':>10}")
    print("-" * 80)
    for r in daily_results:
        avg_load = r['total_tons'] / r['total_trucks'] if r['total_trucks'] > 0 else 0
        print(f"Day {r['day']:<5} {r['shipments']:>8} {r['total_tons']:>12.2f} {r['total_trucks']:>8} {avg_load:>10.1f}")
    
    print(f"\n合同累计完成:")
    for cid, total in sorted(contract_progress.items()):
        print(f"  {cid}: {total:.2f} 吨")
    
    # 保存汇总报告
    summary_file = Path(f"./state/multi_day_summary.json")
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump({
            'test_date': datetime.now().isoformat(),
            'start_day': start_day,
            'num_days': num_days,
            'daily_results': daily_results,
            'contract_progress': contract_progress,
            'summary': {
                'total_days': len(daily_results),
                'total_tons': total_tons_all,
                'total_trucks': total_trucks_all,
                'avg_daily_tons': avg_daily_tons,
            }
        }, f, indent=2, ensure_ascii=False, default=str)
    
    print(f"\n汇总报告已保存：{summary_file}")
    print(f"\n{'=' * 80}")
    print("测试完成")
    print(f"{'=' * 80}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="多日连续运行测试")
    parser.add_argument("--start-day", type=int, default=10, help="起始日")
    parser.add_argument("--days", type=int, default=5, help="运行天数")
    args = parser.parse_args()
    
    run_multi_day_test(start_day=args.start_day, num_days=args.days)
