#!/usr/bin/env python3
"""
test_with_mock_data.py

使用模拟数据测试模型运行

功能：
1. 创建模拟合同数据（用于 PD API 缓存）
2. 初始化模型状态
3. 运行滚动优化
4. 验证输出结果

使用方式：
    python3 test_with_mock_data.py --today 10
"""

import sys
import json
import os
from datetime import datetime
from pathlib import Path

# 添加当前目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from common_utils_v2 import Contract
from state_manager import StateManager


def create_mock_contracts():
    """
    创建模拟合同数据
    
    返回:
        合同列表（PD API 格式）
    """
    print("创建模拟合同数据...")
    
    contracts = [
        {
            "id": 1,
            "contract_no": "HT-2026-001",
            "contract_date": "2026-03-01",
            "end_date": "2026-03-20",
            "smelter_company": "R1",
            "total_quantity": 520.0,
            "truck_count": 0,
            "arrival_payment_ratio": 0.9,
            "final_payment_ratio": 0.1,
            "status": "生效中",
            "products": [
                {"product_name": "A", "unit_price": 520.0},
                {"product_name": "B", "unit_price": 500.0}
            ]
        },
        {
            "id": 2,
            "contract_no": "HT-2026-002",
            "contract_date": "2026-03-05",
            "end_date": "2026-03-25",
            "smelter_company": "R2",
            "total_quantity": 900.0,
            "truck_count": 0,
            "arrival_payment_ratio": 0.9,
            "final_payment_ratio": 0.1,
            "status": "生效中",
            "products": [
                {"product_name": "A", "unit_price": 530.0},
                {"product_name": "B", "unit_price": 510.0}
            ]
        }
    ]
    
    print(f"  创建 {len(contracts)} 个合同")
    return contracts


def cache_mock_contracts(contracts):
    """
    缓存模拟合同到文件
    
    参数:
        contracts: 合同列表（PD API 格式）
    """
    print("缓存模拟合同到 state/contracts_cache.json...")
    
    # 转换为内部格式并缓存
    cache_data = []
    for pc in contracts:
        # 日期转换为 day 编号
        base = datetime(2026, 1, 1)
        start_dt = datetime.strptime(pc["contract_date"], "%Y-%m-%d")
        end_dt = datetime.strptime(pc["end_date"], "%Y-%m-%d")
        start_day = (start_dt - base).days + 1
        end_day = (end_dt - base).days + 1
        
        # 提取品类
        allowed_categories = [p["product_name"] for p in pc["products"]]
        
        cache_data.append({
            "cid": pc["contract_no"],
            "receiver": pc["smelter_company"],
            "Q": pc["total_quantity"],
            "start_day": start_day,
            "end_day": end_day,
            "allowed_categories": allowed_categories,
        })
    
    # 确保 state 目录存在
    state_dir = Path(__file__).parent / "state"
    state_dir.mkdir(exist_ok=True)
    
    # 写入缓存文件
    cache_file = state_dir / "contracts_cache.json"
    with open(cache_file, 'w', encoding='utf-8') as f:
        json.dump(cache_data, f, indent=2, ensure_ascii=False)
    
    print(f"  缓存文件：{cache_file}")
    print(f"  缓存合同数：{len(cache_data)}")
    
    return cache_data


def initialize_state(today=10):
    """
    初始化模型状态
    
    参数:
        today: 今日（day 编号）
    """
    print(f"\n初始化模型状态（today={today}）...")
    
    state_mgr = StateManager("./state")
    
    # 初始已到货量
    delivered_so_far = {
        "HT-2026-001": 0.0,
        "HT-2026-002": 0.0,
    }
    
    # 初始在途报单（模拟一些在途数据）
    in_transit_orders = [
        {
            "order_id": "DL001",
            "cid": "HT-2026-001",
            "warehouse": "W1",
            "category": "A",
            "ship_day": today - 1,  # 昨日发货
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
    
    # 保存状态
    state_mgr.update_state(
        delivered_so_far=delivered_so_far,
        in_transit_orders=in_transit_orders,
        x_prev={},
        today=today - 1,
    )
    
    print(f"  已到货：{delivered_so_far}")
    print(f"  在途报单：{len(in_transit_orders)} 单")
    print("  状态初始化完成")


def run_optimization(today=10, H=10):
    """
    运行滚动优化
    
    参数:
        today: 今日（day 编号）
        H: 规划窗口（天数）
    
    返回:
        优化结果
    """
    print(f"\n运行滚动优化（today={today}, H={H}）...")
    
    from rolling_optimizer import RollingOptimizer
    
    optimizer = RollingOptimizer(
        state_dir="./state",
        api_base_url="http://127.0.0.1:8007",
    )
    
    try:
        result = optimizer.run(today=today, H=H)
        print("  优化成功！")
        return result
    except Exception as e:
        print(f"  优化失败：{e}")
        raise


def verify_result(result):
    """
    验证优化结果
    
    参数:
        result: 优化结果
    
    返回:
        验证是否通过
    """
    print("\n验证优化结果...")
    
    # 检查 x_today
    x_today = result.get("x_today", {})
    if not x_today:
        print("  警告：今日计划为空")
        return False
    
    print(f"  今日计划记录数：{len(x_today)}")
    
    # 检查 trucks
    trucks = result.get("trucks", {})
    print(f"  建议车数记录数：{len(trucks)}")
    
    # 检查 mixing
    mixing = result.get("mixing", {})
    print(f"  混装明细记录数：{len(mixing)}")
    
    # 检查 arrival_plan
    arrival_plan = result.get("arrival_plan", {})
    print(f"  到货计划记录数：{len(arrival_plan)}")
    
    # 打印部分结果
    print("\n  今日计划示例:")
    for i, (key, value) in enumerate(list(x_today.items())[:3]):
        print(f"    {key}: {value} 吨")
    
    if trucks:
        print("\n  车数建议示例:")
        for key, value in list(trucks.items())[:3]:
            print(f"    {key}: {value} 车")
    
    print("\n  验证通过")
    return True


def save_test_report(result, today=10):
    """
    保存测试报告
    
    参数:
        result: 优化结果
        today: 今日（day 编号）
    """
    print("\n保存测试报告...")
    
    report_file = f"./state/test_report_day{today}.json"
    
    report = {
        "test_date": datetime.now().isoformat(),
        "today": today,
        "result": result,
        "summary": {
            "total_shipments": len(result.get("x_today", {})),
            "total_trucks": len(result.get("trucks", {})),
            "total_mixing": len(result.get("mixing", {})),
            "total_arrival_plan": len(result.get("arrival_plan", {})),
        }
    }
    
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)
    
    print(f"  报告文件：{report_file}")


def main():
    """主测试流程"""
    print("=" * 60)
    print("PreModels v2 模拟数据测试")
    print("=" * 60)
    
    # 解析参数
    import argparse
    parser = argparse.ArgumentParser(description="模拟数据测试")
    parser.add_argument("--today", type=int, default=10, help="今日 (day)")
    parser.add_argument("--H", type=int, default=10, help="规划窗口 (天)")
    args = parser.parse_args()
    
    today = args.today
    H = args.H
    
    try:
        # 1. 创建模拟合同
        print("\n[1/5] 创建模拟数据")
        print("-" * 60)
        mock_contracts = create_mock_contracts()
        cache_mock_contracts(mock_contracts)
        
        # 2. 初始化状态
        print("\n[2/5] 初始化状态")
        print("-" * 60)
        initialize_state(today=today)
        
        # 3. 运行优化
        print("\n[3/5] 运行优化")
        print("-" * 60)
        result = run_optimization(today=today, H=H)
        
        # 4. 验证结果
        print("\n[4/5] 验证结果")
        print("-" * 60)
        if not verify_result(result):
            print("\n测试失败：结果验证未通过")
            sys.exit(1)
        
        # 5. 保存报告
        print("\n[5/5] 保存报告")
        print("-" * 60)
        save_test_report(result, today=today)
        
        # 总结
        print("\n" + "=" * 60)
        print("测试完成")
        print("=" * 60)
        print("\n测试结果:")
        print(f"  - 今日计划：{len(result.get('x_today', {}))} 条")
        print(f"  - 建议车数：{len(result.get('trucks', {}))} 条")
        print(f"  - 混装明细：{len(result.get('mixing', {}))} 条")
        print(f"  - 到货计划：{len(result.get('arrival_plan', {}))} 条")
        print(f"\n报告文件：state/test_report_day{today}.json")
        print("\n测试通过！")
        
    except Exception as e:
        print("\n" + "=" * 60)
        print("测试失败")
        print("=" * 60)
        print(f"\n错误：{e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
