"""
debug_compare.py

对比简化版和完整版的差异，找出问题所在
"""

import sys
from pathlib import Path

v2_dir = Path(__file__).parent.parent
if str(v2_dir) not in sys.path:
    sys.path.insert(0, str(v2_dir))

from models.complex_system_v2 import solve_lp_rolling_H_days
from models.common_utils_v2 import Contract, default_global_delay_pmf
from core.date_utils import DateUtils

print("=" * 80)
print("对比测试：简化版 vs 完整版")
print("=" * 80)

# 测试 1: 无在途 (应该工作)
print("\n【测试 1】无在途报单")
contracts = [
    Contract(cid="HT-001", receiver="R1", Q=1000.0, start_day="2026-03-01", end_day="2026-03-25", products=[{"product_name": "A", "unit_price": 800.0}]),
]

cap_forecast = {(f"W{i}", "A", DateUtils.add_days("2026-03-15", d)): 200.0 for i in [1, 2] for d in range(10)}

result = solve_lp_rolling_H_days(
    warehouses=["W1", "W2"],
    categories=["A"],
    today="2026-03-15",
    H=10,
    contracts=contracts,
    cap_forecast=cap_forecast,
    delivered_so_far={"HT-001": 70.0},
    in_transit_orders=[],  # 空在途
    weight_profile={("W1", "R1", "A"): (35.0, 37.0), ("W2", "R1", "A"): (35.0, 37.0)},
    delay_profile={("W1", "R1"): {0: 0.03, 1: 0.95, 2: 0.02}, ("W2", "R1"): {0: 0.03, 1: 0.95, 2: 0.02}},
    global_delay_pmf=default_global_delay_pmf(),
    x_prev=None,
    stability_weight=0.1,
)

x_today, x_horizon, arrival_plan, trucks, mixing = result
print(f"  x_today: {len(x_today)} 条")
if x_today:
    for k, v in x_today.items():
        print(f"    {k}: {v:.2f} 吨")
else:
    print(f"    ❌ 无发货计划！")

# 测试 2: 有在途 (应该也工作)
print("\n【测试 2】有在途报单")
in_transit = [
    {"order_id": "DL001", "cid": "HT-001", "warehouse": "W1", "category": "A", "ship_day": "2026-03-15", "truck_id": "京 A12345"},
]

result2 = solve_lp_rolling_H_days(
    warehouses=["W1", "W2"],
    categories=["A"],
    today="2026-03-15",
    H=10,
    contracts=contracts,
    cap_forecast=cap_forecast,
    delivered_so_far={"HT-001": 70.0},
    in_transit_orders=in_transit,
    weight_profile={("W1", "R1", "A"): (35.0, 37.0), ("W2", "R1", "A"): (35.0, 37.0)},
    delay_profile={("W1", "R1"): {0: 0.03, 1: 0.95, 2: 0.02}, ("W2", "R1"): {0: 0.03, 1: 0.95, 2: 0.02}},
    global_delay_pmf=default_global_delay_pmf(),
    x_prev=None,
    stability_weight=0.1,
)

x_today2, x_horizon2, arrival_plan2, trucks2, mixing2 = result2
print(f"  x_today: {len(x_today2)} 条")
if x_today2:
    for k, v in x_today2.items():
        print(f"    {k}: {v:.2f} 吨")
else:
    print(f"    ❌ 无发货计划！")

# 测试 3: 多合同 (模拟真实场景)
print("\n【测试 3】多合同场景")
contracts3 = [
    Contract(cid="HT-001", receiver="R1", Q=1000.0, start_day="2026-03-01", end_day="2026-03-25", products=[{"product_name": "A", "unit_price": 800.0}]),
    Contract(cid="HT-002", receiver="R1", Q=800.0, start_day="2026-03-10", end_day="2026-03-30", products=[{"product_name": "A", "unit_price": 820.0}]),
    Contract(cid="HT-003", receiver="R2", Q=500.0, start_day="2026-03-05", end_day="2026-03-18", products=[{"product_name": "A", "unit_price": 790.0}]),
]

result3 = solve_lp_rolling_H_days(
    warehouses=["W1", "W2"],
    categories=["A"],
    today="2026-03-15",
    H=10,
    contracts=contracts3,
    cap_forecast=cap_forecast,
    delivered_so_far={"HT-001": 70.0, "HT-002": 35.5, "HT-003": 0.0},
    in_transit_orders=[
        {"order_id": "DL001", "cid": "HT-001", "warehouse": "W1", "category": "A", "ship_day": "2026-03-15", "truck_id": "京 A12345"},
        {"order_id": "DL002", "cid": "HT-003", "warehouse": "W2", "category": "A", "ship_day": "2026-03-15", "truck_id": "京 B67890"},
    ],
    weight_profile={
        ("W1", "R1", "A"): (35.0, 37.0), ("W2", "R1", "A"): (35.0, 37.0),
        ("W1", "R2", "A"): (34.0, 36.0), ("W2", "R2", "A"): (34.0, 36.0),
    },
    delay_profile={
        ("W1", "R1"): {0: 0.03, 1: 0.95, 2: 0.02}, ("W2", "R1"): {0: 0.03, 1: 0.95, 2: 0.02},
        ("W1", "R2"): {0: 0.03, 1: 0.95, 2: 0.02}, ("W2", "R2"): {0: 0.03, 1: 0.95, 2: 0.02},
    },
    global_delay_pmf=default_global_delay_pmf(),
    x_prev=None,
    stability_weight=0.1,
)

x_today3, x_horizon3, arrival_plan3, trucks3, mixing3 = result3
print(f"  x_today: {len(x_today3)} 条")
if x_today3:
    total = sum(x_today3.values())
    print(f"    总计：{total:.2f} 吨")
    for k, v in sorted(x_today3.items()):
        print(f"    {k[0]}_{k[1]}_{k[2]}: {v:.2f} 吨")
else:
    print(f"    ❌ 无发货计划！")

print(f"\n{'='*80}\n")
