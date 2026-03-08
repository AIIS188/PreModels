#!/usr/bin/env python3
"""
generate_report.py

生成详细的发货计划报告

使用方式：
    python3 generate_report.py --today 10
"""

import json
import sys
from pathlib import Path
from datetime import datetime

def load_plan(today):
    """加载今日计划"""
    plan_file = Path(f"./state/plan_day{today}.json")
    if not plan_file.exists():
        print(f"错误：计划文件不存在：{plan_file}")
        return None
    
    with open(plan_file, 'r', encoding='utf-8') as f:
        return json.load(f)

def load_contracts():
    """加载合同信息"""
    cache_file = Path("./state/contracts_cache.json")
    if not cache_file.exists():
        return {}
    
    with open(cache_file, 'r', encoding='utf-8') as f:
        contracts = json.load(f)
        return {c['cid']: c for c in contracts}

def generate_report(today=10):
    """生成详细报告"""
    print("=" * 80)
    print(f"PreModels v2 发货计划报告")
    print(f"日期：Day {today} (2026-01-{10+today:02d})")
    print(f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    # 加载数据
    plan = load_plan(today)
    if not plan:
        sys.exit(1)
    
    contracts = load_contracts()
    
    # 合同汇总信息
    print("\n【合同执行概况】")
    print("-" * 80)
    
    # 统计各合同的发货量
    contract_totals = {}
    for shipment in plan.get('shipments', []):
        cid = shipment['cid']
        tons = shipment['tons']
        contract_totals[cid] = contract_totals.get(cid, 0) + tons
    
    for cid, total in contract_totals.items():
        contract = contracts.get(cid, {})
        receiver = contract.get('receiver', 'Unknown')
        total_qty = contract.get('Q', 0)
        progress = (total / total_qty * 100) if total_qty > 0 else 0
        
        print(f"合同 {cid}:")
        print(f"  收货方：{receiver}")
        print(f"  合同总量：{total_qty} 吨")
        print(f"  今日计划：{total:.2f} 吨")
        print(f"  完成进度：{progress:.1f}%")
        print()
    
    # 发货计划详情
    print("\n【今日发货计划详情】")
    print("-" * 80)
    print(f"{'序号':<4} {'仓库':<6} {'合同号':<15} {'品类':<6} {'吨数':>10} {'车数':>6} {'收货方':<10}")
    print("-" * 80)
    
    shipments = plan.get('shipments', [])
    trucks_map = {
        f"{t['warehouse']}_{t['cid']}_{t.get('day', today)}": t 
        for t in plan.get('trucks', [])
    }
    
    for i, shipment in enumerate(shipments, 1):
        warehouse = shipment['warehouse']
        cid = shipment['cid']
        category = shipment['category']
        tons = shipment['tons']
        
        # 查找对应的车数
        truck_key = f"{warehouse}_{cid}_{today}"
        truck_info = trucks_map.get(truck_key, {})
        truck_count = truck_info.get('trucks', 0)
        
        # 查找收货方
        contract = contracts.get(cid, {})
        receiver = contract.get('receiver', 'Unknown')
        
        print(f"{i:<4} {warehouse:<6} {cid:<15} {category:<6} {tons:>10.2f} {truck_count:>6} {receiver:<10}")
    
    print("-" * 80)
    print(f"合计：{len(shipments)} 条记录，总吨数：{sum(s['tons'] for s in shipments):.2f} 吨")
    
    # 仓库汇总
    print("\n【仓库发货汇总】")
    print("-" * 80)
    
    warehouse_totals = {}
    for shipment in shipments:
        wh = shipment['warehouse']
        warehouse_totals[wh] = warehouse_totals.get(wh, 0) + shipment['tons']
    
    for wh, total in sorted(warehouse_totals.items()):
        truck_count = sum(
            t['trucks'] for t in plan.get('trucks', []) 
            if t['warehouse'] == wh
        )
        print(f"仓库 {wh}: {total:.2f} 吨，{truck_count} 车")
    
    # 品类汇总
    print("\n【品类发货汇总】")
    print("-" * 80)
    
    category_totals = {}
    for shipment in shipments:
        cat = shipment['category']
        category_totals[cat] = category_totals.get(cat, 0) + shipment['tons']
    
    for cat, total in sorted(category_totals.items()):
        print(f"品类 {cat}: {total:.2f} 吨")
    
    # 混装详情
    mixing_details = plan.get('mixing', [])
    if mixing_details and any(m.get('mixing') for m in mixing_details):
        print("\n【混装明细】")
        print("-" * 80)
        
        for mixing in mixing_details:
            warehouse = mixing['warehouse']
            cid = mixing['cid']
            mixing_dict = mixing.get('mixing', {})
            
            if len(mixing_dict) > 1:
                print(f"{warehouse} -> {cid}: 混装")
                for cat, tons in mixing_dict.items():
                    print(f"  - 品类 {cat}: {tons:.2f} 吨")
    
    # 优化建议
    print("\n【优化建议】")
    print("-" * 80)
    
    total_tons = sum(s['tons'] for s in shipments)
    total_trucks = sum(t['trucks'] for t in plan.get('trucks', []))
    avg_load = total_tons / total_trucks if total_trucks > 0 else 0
    
    print(f"1. 平均载重：{avg_load:.2f} 吨/车")
    print(f"   - 基准载重：35 吨/车")
    if avg_load > 35:
        print(f"   - 状态：优秀（高于基准 {((avg_load/35)-1)*100:.1f}%）")
    elif avg_load > 32:
        print(f"   - 状态：良好")
    else:
        print(f"   - 状态：需改进（低于基准 {((1-avg_load/35)*100):.1f}%）")
    
    # 合同完成预警
    print("\n2. 合同完成预警:")
    for cid, total in contract_totals.items():
        contract = contracts.get(cid, {})
        total_qty = contract.get('Q', 0)
        end_day = contract.get('end_day', 0)
        remaining_qty = total_qty - total
        remaining_days = end_day - today
        
        if remaining_days > 0:
            daily_needed = remaining_qty / remaining_days
            print(f"   - {cid}: 剩余 {remaining_qty:.1f} 吨/{remaining_days} 天 = {daily_needed:.1f} 吨/天")
        else:
            print(f"   - {cid}: ⚠️  合同即将到期！剩余 {remaining_qty:.1f} 吨")
    
    # 总结
    print("\n" + "=" * 80)
    print("报告结束")
    print("=" * 80)
    
    # 返回结构化数据
    return {
        'date': today,
        'total_shipments': len(shipments),
        'total_tons': total_tons,
        'total_trucks': total_trucks,
        'avg_load': avg_load,
        'shipments': shipments,
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="生成发货计划报告")
    parser.add_argument("--today", type=int, default=10, help="今日 (day)")
    args = parser.parse_args()
    
    generate_report(args.today)
