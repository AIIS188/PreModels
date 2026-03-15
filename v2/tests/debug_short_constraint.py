"""
debug_short_constraint.py

调试 ShortDef 约束，看为什么 short=0
"""

import sys
from pathlib import Path

v2_dir = Path(__file__).parent.parent
if str(v2_dir) not in sys.path:
    sys.path.insert(0, str(v2_dir))

from models.common_utils_v2 import Contract, default_global_delay_pmf, predict_intransit_arrivals_expected
from core.date_utils import DateUtils

c = Contract(cid="HT-001", receiver="R1", Q=1000.0, start_day="2026-03-01", end_day="2026-03-25", products=[{"product_name": "A", "unit_price": 800.0}])

delivered = 70.0
today = "2026-03-15"

# 假设有在途
in_transit = [
    {"order_id": "DL001", "cid": "HT-001", "warehouse": "W1", "category": "A", "ship_day": "2026-03-15", "truck_id": "京 A12345"},
]

weight_profile = {("W1", "R1", "A"): (35.0, 37.0)}
delay_profile = {("W1", "R1"): {0: 0.03, 1: 0.95, 2: 0.02}}

pred_mu, pred_hi = predict_intransit_arrivals_expected(
    contracts=[c],
    in_transit_orders=in_transit,
    weight_profile=weight_profile,
    delay_profile=delay_profile,
    global_delay_pmf=default_global_delay_pmf(),
)

print("=" * 80)
print("ShortDef 约束分析")
print("=" * 80)

print(f"\n合同：{c.cid}")
print(f"  合同总量：{c.Q} 吨")
print(f"  95% 目标：{0.95 * c.Q} 吨")
print(f"  已到货：{delivered} 吨")
print(f"  剩余需求：{0.95 * c.Q - delivered} 吨")

# 计算 future_intransit (今天之后的在途预测)
future_intransit_mu = 0.0
d = DateUtils.add_days(today, 1)
while DateUtils.diff_days(d, c.end_day) >= 0:
    val = pred_mu.get((c.cid, d), 0.0)
    if val > 0:
        print(f"  在途预测 {d}: {val:.2f} 吨")
    future_intransit_mu += val
    d = DateUtils.add_days(d, 1)

print(f"\n在途预测总计 (未来): {future_intransit_mu:.2f} 吨")

# ShortDef 约束
# short >= 0.95 * Q - (delivered + future_intransit + A_new)
# 当 x=0 时，A_new=0
# short >= 0.95 * Q - (delivered + future_intransit)

rhs = 0.95 * c.Q - (delivered + future_intransit_mu)
print(f"\nShortDef 约束 (当 x=0 时):")
print(f"  short >= {0.95 * c.Q} - ({delivered} + {future_intransit_mu:.2f} + 0)")
print(f"  short >= {rhs:.2f}")

if rhs <= 0:
    print(f"\n⚠️  问题：RHS <= 0，short 可以为 0！")
    print(f"   模型认为在途已经足够满足合同需求")
else:
    print(f"\n✅ RHS > 0，short 必须 > 0")

print(f"\n{'='*80}\n")
