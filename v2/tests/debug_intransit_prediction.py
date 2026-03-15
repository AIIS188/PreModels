"""
debug_intransit_prediction.py

调试在途预测逻辑，查看是否因为在途量过大导致无需新发货
"""

import sys
from pathlib import Path

v2_dir = Path(__file__).parent.parent
if str(v2_dir) not in sys.path:
    sys.path.insert(0, str(v2_dir))

from models.common_utils_v2 import Contract, predict_intransit_arrivals_expected, default_global_delay_pmf
from core.date_utils import DateUtils

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

in_transit_orders = [
    {"order_id": "DL202", "cid": "HT-001", "warehouse": "W1", "category": "A", "ship_day": "2026-03-15", "truck_id": "京 D22222"},
    {"order_id": "DL203", "cid": "HT-001", "warehouse": "W2", "category": "A", "ship_day": "2026-03-15", "truck_id": "京 E33333"},
    {"order_id": "DL206", "cid": "HT-003", "warehouse": "W1", "category": "A", "ship_day": "2026-03-14", "truck_id": "京 G55555"},
    {"order_id": "DL207", "cid": "HT-003", "warehouse": "W2", "category": "A", "ship_day": "2026-03-15", "truck_id": "京 H66666"},
]

weight_profile = {
    ("W1", "R1", "A"): (35.0, 37.0),
    ("W1", "R2", "A"): (34.0, 36.0),
    ("W2", "R1", "A"): (35.0, 37.0),
    ("W2", "R2", "A"): (34.0, 36.0),
}

delay_profile = {
    ("W1", "R1"): {0: 0.03, 1: 0.95, 2: 0.02},
    ("W1", "R2"): {0: 0.03, 1: 0.95, 2: 0.02},
    ("W2", "R1"): {0: 0.03, 1: 0.95, 2: 0.02},
    ("W2", "R2"): {0: 0.03, 1: 0.95, 2: 0.02},
}

today = "2026-03-15"

print("=" * 80)
print("在途预测分析")
print("=" * 80)

pred_mu, pred_hi = predict_intransit_arrivals_expected(
    contracts=contracts,
    in_transit_orders=in_transit_orders,
    weight_profile=weight_profile,
    delay_profile=delay_profile,
    global_delay_pmf=default_global_delay_pmf(),
)

print(f"\n在途报单：{len(in_transit_orders)} 单")
for o in in_transit_orders:
    print(f"  - {o['order_id']} ({o['cid']}): {o.get('weight', 35)} 吨，ship_day={o['ship_day']}")

print(f"\n在途预测 (期望值 pred_mu):")
for cid in ["HT-001", "HT-003"]:
    total = 0.0
    print(f"\n{cid}:")
    for d in range(5):
        date = DateUtils.add_days(today, d)
        val = pred_mu.get((cid, date), 0.0)
        if val > 0:
            print(f"  {date}: {val:.2f} 吨")
            total += val
    print(f"  总计：{total:.2f} 吨")
    
    # 合同需求
    contract = next(c for c in contracts if c.cid == cid)
    delivered = 70.0 if cid == "HT-001" else 0.0
    remaining = 0.95 * contract.Q - delivered
    print(f"  合同剩余需求：{remaining:.2f} 吨")
    print(f"  在途覆盖比例：{total / remaining * 100:.1f}%")

print(f"\n{'='*80}\n")
