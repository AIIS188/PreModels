"""
debug_lp_model.py

调试 LP 模型，检查变量和约束
"""

import sys
from pathlib import Path
import pulp

v2_dir = Path(__file__).parent.parent
if str(v2_dir) not in sys.path:
    sys.path.insert(0, str(v2_dir))

from models.common_utils_v2 import Contract, default_global_delay_pmf, get_delay_dist, predict_intransit_arrivals_expected
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
]

warehouses = ["W1"]
categories = ["A"]
today = "2026-03-15"
H = 3

cap_forecast = {
    ("W1", "A", "2026-03-15"): 200.0,
    ("W1", "A", "2026-03-16"): 200.0,
    ("W1", "A", "2026-03-17"): 200.0,
}

delivered_so_far = {"HT-001": 70.0}

in_transit_orders = [
    {"order_id": "DL202", "cid": "HT-001", "warehouse": "W1", "category": "A", "ship_day": "2026-03-15", "weight": 35.0},
]

weight_profile = {("W1", "R1", "A"): (35.0, 37.0)}
delay_profile = {("W1", "R1"): {0: 0.03, 1: 0.95, 2: 0.02}}

print("=" * 80)
print("LP 模型调试")
print("=" * 80)

# 1. 在途预测
pred_mu, pred_hi = predict_intransit_arrivals_expected(
    contracts=contracts,
    in_transit_orders=in_transit_orders,
    weight_profile=weight_profile,
    delay_profile=delay_profile,
    global_delay_pmf=default_global_delay_pmf(),
)

print(f"\n在途预测:")
for d in range(3):
    date = DateUtils.add_days(today, d)
    val = pred_mu.get(("HT-001", date), 0.0)
    print(f"  {date}: {val:.2f} 吨")

# 2. 创建模型
model = pulp.LpProblem("Test_LP", pulp.LpMinimize)

# 3. 创建变量
x = {}
for c in contracts:
    for k in categories:
        if k not in c.allowed_categories:
            print(f"\n⚠️  品类 {k} 不在合同 {c.cid} 的 allowed_categories 中")
            print(f"   allowed_categories = {c.allowed_categories}")
            continue
        for t in [DateUtils.add_days(today, d) for d in range(H)]:
            for w in warehouses:
                x[(w, c.cid, k, t)] = pulp.LpVariable(f"x_{w}_{c.cid}_{k}_{t}", lowBound=0, cat="Continuous")

print(f"\n创建变量：{len(x)} 个")
for key in list(x.keys())[:5]:
    print(f"  {key}: {x[key]}")

# 4. 能力约束
for w in warehouses:
    for k in categories:
        for t in [DateUtils.add_days(today, d) for d in range(H)]:
            cap = float(cap_forecast.get((w, k, t), 0.0))
            expr = [x[(w, c.cid, k, t)] for c in contracts if (w, c.cid, k, t) in x]
            if expr:
                model += (pulp.lpSum(expr) <= cap, f"Cap_{w}_{k}_{t}")

print(f"\n能力约束：{len(model.constraints)} 个")

# 5. 目标函数（简化版：最小化缺口）
c = contracts[0]
delivered = delivered_so_far.get(c.cid, 0.0)
T = DateUtils.diff_days(today, c.end_day) + 1
R = max(0.0, 0.95 * c.Q - delivered)
target_daily = R / T

print(f"\n合同 {c.cid}:")
print(f"  已到货：{delivered} 吨")
print(f"  剩余需求：{R} 吨")
print(f"  剩余天数：{T} 天")
print(f"  日均目标：{target_daily:.2f} 吨")

# 新增发货表达式
A_new = {}
for d in [DateUtils.add_days(today, i) for i in range(H)]:
    expr_terms = []
    for t in [DateUtils.add_days(today, j) for j in range(H)]:
        delta = DateUtils.diff_days(t, d)
        if delta < 0:
            continue
        for w in warehouses:
            dist = get_delay_dist(w, c.receiver, delay_profile=delay_profile, global_delay_pmf=default_global_delay_pmf())
            p = float(dist.get(delta, 0.0))
            if p <= 0:
                continue
            key = (w, c.cid, categories[0], t)
            if key in x:
                expr_terms.append(x[key] * p)
    if expr_terms:
        A_new[(c.cid, d)] = pulp.lpSum(expr_terms)

print(f"\n新增发货表达式：{len(A_new)} 个")

# 缺口变量
short = pulp.LpVariable(f"short_{c.cid}", lowBound=0)

# 计算期望总到货
future_intransit_mu = sum(pred_mu.get((c.cid, DateUtils.add_days(today, i)), 0.0) for i in range(1, T))
add_valid_expr = pulp.lpSum([A_new[(c.cid, d)] for d in A_new.keys()])

expected_total = delivered + future_intransit_mu + add_valid_expr
model += (short >= 0.95 * c.Q - expected_total, f"ShortDef_{c.cid}")

print(f"\n在途预测 (未来): {future_intransit_mu:.2f} 吨")
print(f"目标函数：最小化 short")
model += short

# 6. 求解
print(f"\n求解中...")
model.solve(pulp.PULP_CBC_CMD(msg=False))

print(f"求解状态：{pulp.LpStatus[model.status]}")

# 7. 输出
print(f"\n结果:")
for key, var in x.items():
    val = var.value()
    if val and val > 1e-6:
        print(f"  {key}: {val:.2f} 吨")

print(f"\nshort = {short.value():.2f}")

print(f"\n{'='*80}\n")
