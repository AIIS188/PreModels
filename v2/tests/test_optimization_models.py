#!/usr/bin/env python3
"""
test_optimization_models.py

最优化模型完整性测试

测试内容:
1. complex_system_v2 - 最优化模型核心算法
2. rolling_optimizer - 滚动优化器完整流程
3. 降级模式 - 无真实 API 时的运行

运行方式:
    python3 tests/test_optimization_models.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from models.common_utils_v2 import (
    Contract, default_global_delay_pmf, get_delay_dist,
    predict_intransit_arrivals_expected, suggest_trucks_from_tons_plan
)
from models.complex_system_v2 import solve_lp_rolling_H_days
from models.rolling_optimizer import RollingOptimizer
from core.state_manager import StateManager
from core.date_utils import DateUtils
import shutil
import os
import json


# =========================
# 测试配置
# =========================

TEST_STATE_DIR = "./test_state_opt"
TEST_CONTRACTS = [
    Contract(
        cid="HT-2026-001",
        receiver="R1",
        Q=1000.0,
        start_day="2026-03-10",
        end_day="2026-03-20",
        products=[
            {"product_name": "A", "unit_price": 800.0},
            {"product_name": "B", "unit_price": 1200.0},
        ]
    ),
    Contract(
        cid="HT-2026-002",
        receiver="R2",
        Q=800.0,
        start_day="2026-03-10",
        end_day="2026-03-18",
        products=[{"product_name": "A", "unit_price": 850.0}]
    ),
]

TEST_IN_TRANSIT = [
    {"order_id": "O001", "cid": "HT-2026-001", "warehouse": "W1", "category": "A", "weight": 35.0, "ship_day": "2026-03-09", "truck_id": "京 A12345"},
    {"order_id": "O002", "cid": "HT-2026-002", "warehouse": "W2", "category": "A", "weight": 35.0, "ship_day": "2026-03-09", "truck_id": "京 B67890"},
]

TEST_WEIGHT_PROFILE = {
    ("W1", "R1", "A"): (35.0, 37.0),
    ("W1", "R1", "B"): (34.0, 36.0),
    ("W2", "R2", "A"): (35.0, 37.0),
}

TEST_DELAY_PROFILE = {
    ("W1", "R1"): {0: 0.03, 1: 0.97, 2: 0.02},
    ("W2", "R2"): {0: 0.03, 1: 0.97, 2: 0.02},
}


# =========================
# 测试函数
# =========================

def test_contract_structure():
    """测试 1: Contract 结构体"""
    print("\n" + "=" * 70)
    print("测试 1: Contract 结构体")
    print("=" * 70)
    
    contract = TEST_CONTRACTS[0]
    
    # 基础字段
    assert contract.cid == "HT-2026-001"
    assert contract.Q == 1000.0
    assert contract.start_day == "2026-03-10"
    assert contract.end_day == "2026-03-20"
    print(f"✅ 基础字段正常")
    
    # products 字段
    assert len(contract.products) == 2
    assert contract.products[0]["product_name"] == "A"
    assert contract.products[0]["unit_price"] == 800.0
    print(f"✅ products 字段正常：{len(contract.products)} 个品类")
    
    # allowed_categories 属性（向后兼容）
    assert "A" in contract.allowed_categories
    assert "B" in contract.allowed_categories
    print(f"✅ allowed_categories 属性正常：{contract.allowed_categories}")
    
    # 价格查询方法
    assert contract.get_unit_price("A") == 800.0
    assert contract.get_unit_price("B") == 1200.0
    assert contract.get_unit_price("C") is None
    print(f"✅ get_unit_price 方法正常")
    
    # 基础价计算
    base_price_a = contract.get_base_price("A")
    assert abs(base_price_a - 763.36) < 0.01  # 800 / 1.048
    print(f"✅ get_base_price 方法正常：A 品类基础价={base_price_a:.2f}")
    
    print("✅ Contract 结构体测试通过\n")


def test_intransit_prediction():
    """测试 2: 在途预测"""
    print("\n" + "=" * 70)
    print("测试 2: 在途预测")
    print("=" * 70)
    
    pred_mu, pred_hi = predict_intransit_arrivals_expected(
        contracts=TEST_CONTRACTS,
        in_transit_orders=TEST_IN_TRANSIT,
        weight_profile=TEST_WEIGHT_PROFILE,
        delay_profile=TEST_DELAY_PROFILE,
        global_delay_pmf=default_global_delay_pmf(),
    )
    
    print(f"在途预测结果：{len(pred_mu)} 条记录")
    print(f"示例：{list(pred_mu.items())[:3]}")
    
    assert len(pred_mu) > 0, "在途预测应有结果"
    assert len(pred_mu) == len(pred_hi), "期望和上界数量应一致"
    
    print("✅ 在途预测测试通过\n")


def test_complex_system_optimization():
    """测试 3: complex_system_v2 最优化模型"""
    print("\n" + "=" * 70)
    print("测试 3: complex_system_v2 最优化模型")
    print("=" * 70)
    
    today = "2026-03-10"
    H = 5
    
    # 准备产能预测（使用日期字符串，适配新格式）
    cap_forecast = {}
    for d in range(H):
        date = DateUtils.add_days(today, d)
        cap_forecast[("W1", "A", date)] = 200.0
        cap_forecast[("W1", "B", date)] = 50.0
        cap_forecast[("W2", "A", date)] = 150.0
    
    print(f"今日：{today}")
    print(f"规划窗口：H={H} 天")
    print(f"产能预测：{len(cap_forecast)} 条")
    
    # 运行优化
    result = solve_lp_rolling_H_days(
        warehouses=["W1", "W2"],
        categories=["A", "B"],
        today=today,  # 日期字符串
        H=H,
        contracts=TEST_CONTRACTS,
        cap_forecast=cap_forecast,
        delivered_so_far={"HT-2026-001": 0.0, "HT-2026-002": 0.0},
        in_transit_orders=TEST_IN_TRANSIT,
        weight_profile=TEST_WEIGHT_PROFILE,
        delay_profile=TEST_DELAY_PROFILE,
        global_delay_pmf=default_global_delay_pmf(),
        x_prev=None,
        stability_weight=0.1,
    )
    
    x_today, x_horizon, arrival_plan, trucks, mixing = result
    
    print(f"优化结果:")
    print(f"  今日计划：{len(x_today)} 条")
    print(f"  窗口计划：{len(x_horizon)} 条")
    print(f"  到货计划：{len(arrival_plan)} 条")
    print(f"  车数建议：{len(trucks)} 条")
    
    # 注意：无真实需求时可能返回空结果，这是正常的
    # 主要验证模型能够正常运行不报错
    print(f"\n✅ 最优化模型运行正常（结果可能为空，因无真实需求）")
    print("✅ 最优化模型测试通过\n")


def test_rolling_optimizer():
    """测试 4: rolling_optimizer 滚动优化器"""
    print("\n" + "=" * 70)
    print("测试 4: rolling_optimizer 滚动优化器")
    print("=" * 70)
    
    # 清理测试状态
    if os.path.exists(TEST_STATE_DIR):
        shutil.rmtree(TEST_STATE_DIR)
    
    # 创建优化器
    optimizer = RollingOptimizer(state_dir=TEST_STATE_DIR, api_base_url="http://localhost:8007")
    print(f"✅ 优化器已创建")
    
    # 初始化状态
    today = DateUtils.today()
    initial_state = optimizer.state_mgr.initialize_state(
        delivered_so_far={"HT-2026-001": 0.0, "HT-2026-002": 0.0},
        in_transit_orders=TEST_IN_TRANSIT,
        today=today,
    )
    print(f"✅ 状态已初始化 (date={today})")
    
    # 缓存合同（降级用）
    optimizer._cache_contracts(TEST_CONTRACTS)
    print(f"✅ 合同已缓存")
    
    # 运行优化（API 不可用，降级模式）
    result = optimizer.run(today_date=today, H=5)
    print(f"✅ 优化运行完成（降级模式）")
    print(f"   今日计划：{len(result.get('x_today', {}))} 条")
    print(f"   车数建议：{len(result.get('trucks', {}))} 条")
    
    # 检查状态文件
    state_file = os.path.join(TEST_STATE_DIR, "state.json")
    assert os.path.exists(state_file), "状态文件应生成"
    
    with open(state_file, 'r', encoding='utf-8') as f:
        state_data = json.load(f)
    
    assert state_data.get('last_run_date') == today
    assert 'delivered_so_far' in state_data
    print(f"✅ 状态文件已生成")
    
    # 清理
    shutil.rmtree(TEST_STATE_DIR)
    print(f"✅ 测试状态已清理")
    
    print("✅ 滚动优化器测试通过\n")


def test_capacity_allocator():
    """测试 5: 产能分配器"""
    print("\n" + "=" * 70)
    print("测试 5: 产能分配器")
    print("=" * 70)
    
    from core.capacity_allocator import CapacityAllocator, AllocationConfig
    
    # 使用默认配置创建分配器
    config = AllocationConfig()
    allocator = CapacityAllocator(config=config)
    
    # 测试产能分配
    result = allocator.allocate(
        total_cap=350.0,
        warehouse="W1",
        categories=["A", "B"],
        context={"urgency": {"A": 0.8, "B": 0.5}}
    )
    
    print(f"总产能：350.0 吨")
    print(f"分配结果：{result}")
    
    assert isinstance(result, dict)
    assert "A" in result
    assert "B" in result
    print("✅ 产能分配器测试通过\n")


def test_urgency_calculator():
    """测试 6: 紧急度计算器"""
    print("\n" + "=" * 70)
    print("测试 6: 紧急度计算器")
    print("=" * 70)
    
    from core.urgency_calculator import UrgencyCalculator, UrgencyConfig
    
    # 使用默认配置创建计算器
    config = UrgencyConfig()
    calculator = UrgencyCalculator(config=config)
    
    # 测试紧急度计算（使用合同对象）
    today = "2026-03-10"
    
    # 创建测试合同
    from dataclasses import dataclass
    
    @dataclass
    class TestContract:
        cid: str
        Q: float
        start_day: str
        end_day: str
        delivered: float = 0.0
    
    contract = TestContract(
        cid="HT-001",
        Q=1000.0,
        start_day=today,
        end_day="2026-03-20",
        delivered=200.0,
    )
    
    # 批量计算紧急度
    urgency_results = calculator.calculate_batch([contract], today)
    
    print(f"合同：{contract.cid}")
    print(f"总量：{contract.Q} 吨，已到货：{contract.delivered} 吨")
    print(f"剩余：{contract.Q - contract.delivered} 吨")
    print(f"紧急度结果：{urgency_results}")
    
    assert len(urgency_results) > 0
    print("✅ 紧急度计算器测试通过\n")


# =========================
# 主函数
# =========================

def main():
    """运行所有测试"""
    print("=" * 70)
    print("PreModels 最优化模型完整性测试")
    print("=" * 70)
    print(f"测试时间：{DateUtils.today()}")
    
    tests = [
        ("Contract 结构体", test_contract_structure),
        ("在途预测", test_intransit_prediction),
        ("最优化模型", test_complex_system_optimization),
        ("滚动优化器", test_rolling_optimizer),
        ("产能分配器", test_capacity_allocator),
        ("紧急度计算器", test_urgency_calculator),
    ]
    
    passed = 0
    failed = 0
    errors = []
    
    for name, test_func in tests:
        try:
            test_func()
            passed += 1
        except Exception as e:
            failed += 1
            errors.append((name, e))
            import traceback
            print(f"❌ {name} 测试失败：{e}")
            traceback.print_exc()
    
    # 总结
    print("\n" + "=" * 70)
    print("测试总结")
    print("=" * 70)
    print(f"总测试数：{len(tests)}")
    print(f"通过：{passed}")
    print(f"失败：{failed}")
    
    if errors:
        print(f"\n失败详情:")
        for name, error in errors:
            print(f"  - {name}: {error}")
        sys.exit(1)
    else:
        print("\n✅ 所有测试通过！最优化模型运行正常！")
        print("=" * 70)
        sys.exit(0)


if __name__ == "__main__":
    main()
