"""
test_complex_system_direct.py

直接测试 complex_system_v2 的 LP 模型

使用简化的模拟数据，验证模型是否能正常求解
"""

import sys
from pathlib import Path

v2_dir = Path(__file__).parent.parent
if str(v2_dir) not in sys.path:
    sys.path.insert(0, str(v2_dir))

from models.complex_system_v2 import solve_lp_rolling_H_days
from models.common_utils_v2 import Contract, default_global_delay_pmf
from core.date_utils import DateUtils

# 创建测试数据
today = "2026-03-15"
H = 10

contracts = [
    Contract(
        cid="HT-001",
        receiver="R1",
        Q=1000.0,
        start_day="2026-03-01",
        end_day="2026-03-25",
        products=[{"product_name": "A", "unit_price": 800.0}],
    ),
    Contract(
        cid="HT-003",
        receiver="R2",
        Q=500.0,
        start_day="2026-03-05",
        end_day="2026-03-18",
        products=[{"product_name": "A", "unit_price": 790.0}],
    ),
]

warehouses = ["W1", "W2"]
categories = ["A"]

# 产能预测
cap_forecast = {}
for d in range(H):
    date = DateUtils.add_days(today, d)
    cap_forecast[("W1", "A", date)] = 200.0
    cap_forecast[("W2", "A", date)] = 180.0

# 已到货
delivered_so_far = {
    "HT-001": 70.0,
    "HT-003": 0.0,
}

# 在途报单
in_transit_orders = [
    {"order_id": "DL202", "cid": "HT-001", "warehouse": "W1", "category": "A", "ship_day": "2026-03-15", "truck_id": "京 D22222"},
    {"order_id": "DL203", "cid": "HT-001", "warehouse": "W2", "category": "A", "ship_day": "2026-03-15", "truck_id": "京 E33333"},
    {"order_id": "DL206", "cid": "HT-003", "warehouse": "W1", "category": "A", "ship_day": "2026-03-14", "truck_id": "京 G55555"},
    {"order_id": "DL207", "cid": "HT-003", "warehouse": "W2", "category": "A", "ship_day": "2026-03-15", "truck_id": "京 H66666"},
]

# 估重画像
weight_profile = {
    ("W1", "R1", "A"): (35.0, 37.0),
    ("W1", "R2", "A"): (34.0, 36.0),
    ("W2", "R1", "A"): (35.0, 37.0),
    ("W2", "R2", "A"): (34.0, 36.0),
}

# 延迟分布
delay_profile = {
    ("W1", "R1"): {0: 0.03, 1: 0.95, 2: 0.02},
    ("W1", "R2"): {0: 0.03, 1: 0.95, 2: 0.02},
    ("W2", "R1"): {0: 0.03, 1: 0.95, 2: 0.02},
    ("W2", "R2"): {0: 0.03, 1: 0.95, 2: 0.02},
}

print("=" * 80)
print("直接测试 complex_system_v2 LP 模型")
print("=" * 80)

print(f"\n输入数据:")
print(f"  - today: {today}")
print(f"  - H: {H}")
print(f"  - contracts: {len(contracts)} 个")
print(f"  - warehouses: {warehouses}")
print(f"  - categories: {categories}")
print(f"  - delivered_so_far: {delivered_so_far}")
print(f"  - in_transit_orders: {len(in_transit_orders)} 单")

try:
    print(f"\n开始求解...")
    result = solve_lp_rolling_H_days(
        warehouses=warehouses,
        categories=categories,
        today=today,
        H=H,
        contracts=contracts,
        cap_forecast=cap_forecast,
        delivered_so_far=delivered_so_far,
        in_transit_orders=in_transit_orders,
        weight_profile=weight_profile,
        delay_profile=delay_profile,
        global_delay_pmf=default_global_delay_pmf(),
        x_prev=None,
        stability_weight=0.1,
    )
    
    x_today, x_horizon, arrival_plan, trucks, mixing = result
    
    print(f"\n求解成功！")
    print(f"\n结果:")
    print(f"  - x_today (今日发货计划): {len(x_today)} 条")
    for key, val in sorted(x_today.items()):
        print(f"      {key}: {val:.2f} 吨")
    
    print(f"  - x_horizon (窗口计划): {len(x_horizon)} 条")
    print(f"  - arrival_plan (到货诊断): {len(arrival_plan)} 条")
    print(f"  - trucks (车数建议): {len(trucks)} 条")
    print(f"  - mixing (混装明细): {len(mixing)} 条")
    
    if len(x_today) > 0:
        total_tons = sum(x_today.values())
        print(f"\n✅ 今日发货总计：{total_tons:.2f} 吨")
    else:
        print(f"\n⚠️  今日无发货计划")
    
    print(f"\n{'='*80}\n")
    
except Exception as e:
    print(f"\n❌ 求解失败：{e}")
    import traceback
    traceback.print_exc()
