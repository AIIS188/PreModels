#!/usr/bin/env python3
"""
test_with_mock_data.py

模拟数据测试

功能：
1. 创建模拟合同数据
2. 初始化模型状态
3. 运行滚动优化
4. 验证优化结果
5. 生成测试报告

使用方式：
    python3 test_with_mock_data.py --today-date 2026-03-10 --H 5
"""

import sys
import json
from datetime import datetime
from pathlib import Path

# 添加当前目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from models.common_utils_v2 import Contract
from core.state_manager import StateManager
from core.date_utils import DateUtils


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
    
    print(f"  合同数量：{len(contracts)}")
    return contracts


def cache_contracts(contracts):
    """
    缓存合同数据
    
    参数:
        contracts: 合同列表（PD API 格式）
    """
    print("\n缓存合同数据...")
    
    cache_data = []
    for pc in contracts:
        # 提取品类名称
        allowed_categories = [p["product_name"] for p in pc["products"]]
        
        # 使用日期字符串（不再转换）
        start_day = pc["contract_date"]
        end_day = pc["end_date"]
        
        cache_data.append({
            "cid": pc["contract_no"],
            "receiver": pc["smelter_company"],
            "Q": pc["total_quantity"],
            "start_day": start_day,
            "end_day": end_day,
            "products": pc["products"],
        })
    
    # 确保 state 目录存在
    state_dir = Path("./state")
    state_dir.mkdir(exist_ok=True)
    
    # 写入缓存文件
    cache_file = state_dir / "contracts_cache.json"
    with open(cache_file, 'w', encoding='utf-8') as f:
        json.dump(cache_data, f, indent=2, ensure_ascii=False)
    
    print(f"  缓存文件：{cache_file}")
    print(f"  缓存合同数：{len(cache_data)}")
    
    return cache_data


def initialize_state(today_date="2026-03-10"):
    """
    初始化模型状态
    
    参数:
        today_date: 今日日期（YYYY-MM-DD）
    """
    print(f"\n初始化模型状态（date={today_date}）...")
    
    state_mgr = StateManager("./state")
    
    # 初始已到货量
    delivered_so_far = {
        "HT-2026-001": 0.0,
        "HT-2026-002": 0.0,
    }
    
    # 初始在途报单（模拟一些在途数据）
    yesterday = DateUtils.add_days(today_date, -1)
    in_transit_orders = [
        {
            "order_id": "DL001",
            "cid": "HT-2026-001",
            "warehouse": "W1",
            "category": "A",
            "ship_day": yesterday,  # 昨日发货
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
            "ship_day": yesterday,
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
            "ship_day": yesterday,
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
        today=today_date,
    )
    
    print(f"  已到货：{delivered_so_far}")
    print(f"  在途报单：{len(in_transit_orders)} 单")
    print("  状态初始化完成")


def run_optimization(today_date="2026-03-10", H=5):
    """
    运行滚动优化
    
    参数:
        today_date: 今日日期（YYYY-MM-DD）
        H: 规划窗口（天数）
    
    返回:
        优化结果
    """
    print(f"\n运行滚动优化（date={today_date}, H={H}）...")
    
    from models.rolling_optimizer import RollingOptimizer
    
    optimizer = RollingOptimizer(
        state_dir="./state",
        api_base_url="http://127.0.0.1:8007",
    )
    
    try:
        result = optimizer.run(today_date=today_date, H=H)
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
    
    # 检查基本结构
    assert "x_today" in result, "缺少 x_today"
    assert "trucks" in result, "缺少 trucks"
    assert "mixing" in result, "缺少 mixing"
    assert "arrival_plan" in result, "缺少 arrival_plan"
    
    print("  结果结构：OK")
    print(f"    - 今日计划：{len(result['x_today'])} 条")
    print(f"    - 车数建议：{len(result['trucks'])} 条")
    print(f"    - 混装明细：{len(result['mixing'])} 条")
    print(f"    - 到货计划：{len(result['arrival_plan'])} 条")
    
    return True


def save_report(result, today_date):
    """
    保存测试报告
    
    参数:
        result: 优化结果
        today_date: 今日日期
    """
    print("\n保存测试报告...")
    
    date_suffix = today_date.replace("-", "")
    report_file = f"./state/test_report_{date_suffix}.json"
    
    report = {
        "test_date": datetime.now().isoformat(),
        "today_date": today_date,
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
    parser.add_argument("--today-date", type=str, default="2026-03-10", help="今日 (YYYY-MM-DD)")
    parser.add_argument("--H", type=int, default=5, help="规划窗口 (天)")
    args = parser.parse_args()
    
    today_date = args.today_date
    H = args.H
    
    try:
        # 1. 创建合同数据
        contracts = create_mock_contracts()
        
        # 2. 缓存合同
        cache_contracts(contracts)
        
        # 3. 初始化状态
        initialize_state(today_date)
        
        # 4. 运行优化
        result = run_optimization(today_date, H)
        
        # 5. 验证结果
        verify_result(result)
        
        # 6. 保存报告
        save_report(result, today_date)
        
        print("\n" + "=" * 60)
        print("测试通过！")
        print("=" * 60)
        return True
        
    except Exception as e:
        print("\n" + "=" * 60)
        print("测试失败")
        print("=" * 60)
        print(f"\n错误：{e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
