#!/usr/bin/env python3
"""
test_h_impact.py

测试不同 H 值对优化结果的影响

使用方式：
    python3 test_h_impact.py
"""

import sys
import json
import shutil
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from rolling_optimizer import RollingOptimizer
from state_manager import StateManager


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
            "allowed_categories": ["A", "B"],
        },
        {
            "cid": "HT-2026-002",
            "receiver": "R2",
            "Q": 900.0,
            "start_day": 64,
            "end_day": 84,
            "allowed_categories": ["A", "B"],
        },
    ]
    
    cache_file = state_dir / "contracts_cache.json"
    with open(cache_file, 'w', encoding='utf-8') as f:
        json.dump(contracts_cache, f, indent=2, ensure_ascii=False)


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


def test_h_values(today=10, h_values=[5, 10, 15, 20]):
    """
    测试不同 H 值的影响
    
    参数:
        today: 今日
        h_values: 要测试的 H 值列表
    """
    print("=" * 80)
    print("H 值（规划窗口）对优化结果的影响测试")
    print("=" * 80)
    
    results = []
    
    for H in h_values:
        print(f"\n{'=' * 80}")
        print(f"测试 H = {H} 天")
        print(f"{'=' * 80}")
        
        # 重置状态
        reset_state()
        initialize_first_state(today)
        
        # 初始化优化器
        optimizer = RollingOptimizer(
            state_dir="./state",
            api_base_url="http://127.0.0.1:8007",
        )
        
        try:
            # 运行优化
            result = optimizer.run(today=today, H=H)
            
            # 统计结果
            x_today = result.get('x_today', {})
            total_tons = sum(x_today.values())
            total_trucks = sum(result.get('trucks', {}).values())
            
            # 记录结果
            results.append({
                'H': H,
                'total_tons': total_tons,
                'total_trucks': total_trucks,
                'shipments_count': len(x_today),
                'details': {
                    f"{k.split('_')[0]}→{k.split('_')[1]}": v 
                    for k, v in x_today.items()
                }
            })
            
            # 打印结果
            print(f"  今日发货总量：{total_tons:.2f} 吨")
            print(f"  今日发货车数：{total_trucks} 车")
            print(f"  平均载重：{total_tons/total_trucks:.1f} 吨/车" if total_trucks > 0 else "")
            print(f"  发货记录数：{len(x_today)} 条")
            
            print(f"\n  发货明细:")
            for key, tons in sorted(x_today.items()):
                parts = key.split('_')
                if len(parts) == 4:
                    warehouse, cid, category, day = parts
                    print(f"    {warehouse} -> {cid} ({category}): {tons:.2f} 吨")
            
        except Exception as e:
            print(f"  运行失败：{e}")
            results.append({
                'H': H,
                'error': str(e),
            })
    
    # 生成对比报告
    print(f"\n{'=' * 80}")
    print("H 值对比报告")
    print(f"{'=' * 80}")
    
    print(f"\n{'H 值':<8} {'总吨数':>12} {'总车数':>10} {'记录数':>8} {'平均载重':>10}")
    print("-" * 80)
    
    for r in results:
        if 'error' in r:
            print(f"{r['H']:<8} 错误：{r['error'][:30]}")
        else:
            avg_load = r['total_tons'] / r['total_trucks'] if r['total_trucks'] > 0 else 0
            print(f"{r['H']:<8} {r['total_tons']:>12.2f} {r['total_trucks']:>10} {r['shipments_count']:>8} {avg_load:>10.1f}")
    
    # 分析影响
    print(f"\n{'=' * 80}")
    print("影响分析")
    print(f"{'=' * 80}")
    
    if len(results) >= 2:
        valid_results = [r for r in results if 'error' not in r]
        if len(valid_results) >= 2:
            min_tons = min(r['total_tons'] for r in valid_results)
            max_tons = max(r['total_tons'] for r in valid_results)
            diff = max_tons - min_tons
            diff_pct = (diff / min_tons) * 100
            
            print(f"\n1. 今日发货量差异:")
            print(f"   最小值：{min_tons:.2f} 吨 (H={next(r['H'] for r in valid_results if r['total_tons']==min_tons)})")
            print(f"   最大值：{max_tons:.2f} 吨 (H={next(r['H'] for r in valid_results if r['total_tons']==max_tons)})")
            print(f"   差异：{diff:.2f} 吨 ({diff_pct:.1f}%)")
            
            print(f"\n2. 结论:")
            if diff_pct < 5:
                print(f"   H 值对今日发货量影响较小 (<5%)")
                print(f"   建议使用 H=10（平衡性能和远见）")
            elif diff_pct < 15:
                print(f"   H 值对今日发货量影响中等 (5-15%)")
                print(f"   需要根据实际需求选择合适的 H")
            else:
                print(f"   H 值对今日发货量影响显著 (>15%)")
                print(f"   建议仔细评估 H 的选择")
    
    # 保存结果
    summary_file = Path("./state/h_impact_test.json")
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump({
            'test_time': datetime.now().isoformat(),
            'today': today,
            'results': results,
        }, f, indent=2, ensure_ascii=False, default=str)
    
    print(f"\n详细数据已保存：{summary_file}")
    print(f"\n{'=' * 80}")
    print("测试完成")
    print(f"{'=' * 80}")


if __name__ == "__main__":
    test_h_values(today=10, h_values=[5, 10, 15, 20])
