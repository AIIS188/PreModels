"""
debug_lp_detailed.py

详细调试 LP 模型，输出所有变量、约束和目标函数
"""

import sys
from pathlib import Path
import pulp

v2_dir = Path(__file__).parent.parent
if str(v2_dir) not in sys.path:
    sys.path.insert(0, str(v2_dir))

from models.common_utils_v2 import Contract, default_global_delay_pmf, get_delay_dist, predict_intransit_arrivals_expected, calc_purchase_price_per_ton
from core.date_utils import DateUtils

# 简化测试数据
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
H = 5

cap_forecast = {
    ("W1", "A", DateUtils.add_days(today, d)): 200.0 for d in range(H)
}

delivered_so_far = {"HT-001": 70.0}
in_transit_orders = []  # 空在途，测试是否需要新发货

weight_profile = {("W1", "R1", "A"): (35.0, 37.0)}
delay_profile = {("W1", "R1"): {0: 0.03, 1: 0.95, 2: 0.02}}
rho_intransit = 0.9
alpha_short = 3000.0
beta_balance = 2.0
gamma_waste = 80.0

print("=" * 80)
print("LP 模型详细调试")
print("=" * 80)

# 1. 在途预测
pred_mu, pred_hi = predict_intransit_arrivals_expected(
    contracts=contracts,
    in_transit_orders=in_transit_orders,
    weight_profile=weight_profile,
    delay_profile=delay_profile,
    global_delay_pmf=default_global_delay_pmf(),
)

print(f"\n1. 在途预测:")
print(f"   pred_mu: {pred_mu}")

# 2. 发货日窗口
ship_days = list(DateUtils.add_days(today, d) for d in range(H))
print(f"\n2. 发货窗口：{ship_days}")

# 3. 到货日集合
max_delta = max(default_global_delay_pmf().keys())
arrival_days_set = set()
for t in ship_days:
    for d in range(max_delta + 1):
        arrival_days_set.add(DateUtils.add_days(t, d))

c = contracts[0]
date = c.start_day
while DateUtils.diff_days(date, c.end_day) >= 0:
    arrival_days_set.add(date)
    date = DateUtils.add_days(date, 1)

arrival_days = sorted(arrival_days_set)
print(f"3. 到货日集合：{len(arrival_days)} 天")
print(f"   范围：{arrival_days[0]} 到 {arrival_days[-1]}")

# 4. 创建模型
model = pulp.LpProblem("RollingH_LP_Debug", pulp.LpMinimize)

# 5. 决策变量
x = {}
for w in warehouses:
    for contract in contracts:
        for k in categories:
            if k not in contract.allowed_categories:
                print(f"⚠️  品类 {k} 不在合同 {contract.cid} 的允许范围内")
                continue
            for t in ship_days:
                x[(w, contract.cid, k, t)] = pulp.LpVariable(
                    f"x_{w}_{contract.cid}_{k}_{t.replace('-', '')}", lowBound=0, cat="Continuous"
                )

print(f"\n4. 决策变量：{len(x)} 个")
for key, var in list(x.items())[:5]:
    print(f"   {key}: {var.name}")

# 6. 能力约束
cap_constraints = 0
for w in warehouses:
    for k in categories:
        for t in ship_days:
            cap = float(cap_forecast.get((w, k, t), 0.0))
            expr = []
            for contract in contracts:
                key = (w, contract.cid, k, t)
                if key in x:
                    expr.append(x[key])
            if expr:
                model += (pulp.lpSum(expr) <= cap, f"Cap_{w}_{k}_{t.replace('-', '')}")
                cap_constraints += 1

print(f"\n5. 能力约束：{cap_constraints} 个")

# 7. 新增发货映射到到货日 A_new
A_new = {}
waste_exp = {}

for contract in contracts:
    waste_terms = []
    for d in arrival_days:
        expr_terms = []
        for t in ship_days:
            delta = DateUtils.diff_days(t, d)
            if delta < 0:
                continue
            for w in warehouses:
                dist = get_delay_dist(w, contract.receiver, delay_profile=delay_profile, global_delay_pmf=default_global_delay_pmf())
                p = float(dist.get(delta, 0.0))
                if p <= 0:
                    continue
                for k in categories:
                    key = (w, contract.cid, k, t)
                    if key in x:
                        expr_terms.append(x[key] * p)
        if expr_terms:
            A_new[(contract.cid, d)] = pulp.lpSum(expr_terms)
            if DateUtils.diff_days(d, contract.end_day) < 0:
                waste_terms.append(A_new[(contract.cid, d)])
    waste_exp[contract.cid] = pulp.lpSum(waste_terms) if waste_terms else 0

print(f"\n6. A_new 表达式：{len(A_new)} 个")
print(f"   waste_exp: {waste_exp}")

# 8. 缺口与均衡偏差
short = {}
dev_pos = {}
dev_neg = {}

for contract in contracts:
    cid = contract.cid
    delivered = float(delivered_so_far.get(cid, 0.0))
    
    # 计算剩余有效天数
    remain_start = today if DateUtils.diff_days(today, contract.start_day) > 0 else contract.start_day
    if DateUtils.diff_days(remain_start, contract.end_day) < 0:
        print(f"\n⚠️  合同 {cid} 已过期或今天就是最后一天")
        continue
    
    T = DateUtils.diff_days(remain_start, contract.end_day) + 1
    if T <= 0:
        continue
    
    # 在途预测（有效期内，未来）
    future_intransit_mu = 0.0
    future_intransit_hi = 0.0
    d = DateUtils.add_days(today, 1)
    while DateUtils.diff_days(d, contract.end_day) >= 0:
        future_intransit_mu += float(pred_mu.get((cid, d), 0.0))
        future_intransit_hi += float(pred_hi.get((cid, d), 0.0))
        d = DateUtils.add_days(d, 1)
    
    # 新增发货（有效期内）
    add_valid_terms = []
    d = today
    while DateUtils.diff_days(d, contract.end_day) >= 0:
        expr = A_new.get((cid, d), None)
        if expr is not None:
            add_valid_terms.append(expr)
        d = DateUtils.add_days(d, 1)
    add_valid_expr = pulp.lpSum(add_valid_terms) if add_valid_terms else 0
    
    # q_star
    R = max(0.0, 0.95 * contract.Q - delivered - rho_intransit * future_intransit_mu)
    target_daily = R / T
    q_star = target_daily + (rho_intransit * future_intransit_mu) / T
    
    print(f"\n7. 合同 {cid} 分析:")
    print(f"   已到货：{delivered} 吨")
    print(f"   在途预测 (未来): {future_intransit_mu:.2f} 吨")
    print(f"   剩余需求 R: {R:.2f} 吨")
    print(f"   剩余天数 T: {T} 天")
    print(f"   日均目标：{target_daily:.2f} 吨")
    print(f"   q_star: {q_star:.2f} 吨")
    print(f"   新增发货表达式项数：{len(add_valid_terms)}")
    
    # 缺口
    short[cid] = pulp.LpVariable(f"short_{cid}", lowBound=0)
    expected_total = delivered + future_intransit_mu + add_valid_expr
    model += (short[cid] >= 0.95 * contract.Q - expected_total, f"ShortDef_{cid}")
    
    print(f"   期望总到货 = {delivered} + {future_intransit_mu:.2f} + A_new")
    print(f"   缺口约束：short >= {0.95 * contract.Q} - ({delivered} + {future_intransit_mu:.2f} + A_new)")
    
    # 超发约束
    model += (delivered + future_intransit_hi + add_valid_expr <= 1.05 * contract.Q, f"OverCap_{cid}")
    
    # 均衡偏差
    d = today
    while DateUtils.diff_days(d, contract.end_day) >= 0:
        add_expr = A_new.get((cid, d), 0)
        dev_pos[(cid, d)] = pulp.LpVariable(f"dev_pos_{cid}_{d.replace('-', '')}", lowBound=0)
        dev_neg[(cid, d)] = pulp.LpVariable(f"dev_neg_{cid}_{d.replace('-', '')}", lowBound=0)
        model += (add_expr - target_daily == dev_pos[(cid, d)] - dev_neg[(cid, d)], f"Balance_{cid}_{d.replace('-', '')}")
        d = DateUtils.add_days(d, 1)

# 9. 目标函数
obj_short = pulp.lpSum(short.values()) if short else 0
obj_balance = (pulp.lpSum(dev_pos.values()) + pulp.lpSum(dev_neg.values())) if dev_pos else 0
obj_waste = pulp.lpSum(waste_exp.values()) if waste_exp else 0

print(f"\n8. 目标函数:")
print(f"   alpha_short * obj_short = {alpha_short} * short")
print(f"   beta_balance * obj_balance = {beta_balance} * balance")
print(f"   gamma_waste * obj_waste = {gamma_waste} * waste")

model += (alpha_short * obj_short + beta_balance * obj_balance + gamma_waste * obj_waste)

# 10. 求解
print(f"\n9. 求解中...")
model.solve(pulp.PULP_CBC_CMD(msg=0))

print(f"\n10. 求解状态：{pulp.LpStatus[model.status]}")

# 11. 输出结果
print(f"\n11. 结果:")
print(f"    变量总数：{len(x)}")
print(f"    非零变量:")

non_zero_count = 0
for key, var in sorted(x.items()):
    val = var.value()
    if val and val > 1e-6:
        print(f"      {key}: {val:.2f} 吨")
        non_zero_count += 1

if non_zero_count == 0:
    print(f"      (无)")

print(f"\n    short 值:")
for cid, s in short.items():
    print(f"      short_{cid} = {s.value():.2f}")

print(f"\n    目标函数值：{pulp.value(model.objective):.2f}")

# 12. 分析为什么 x=0
print(f"\n{'='*80}")
print(f"分析：为什么 x=0 是最优解？")
print(f"{'='*80}")

# 如果 x=0，计算目标函数值
obj_at_zero = alpha_short * (0.95 * c.Q - delivered_so_far['HT-001'])  # 只有缺口项
print(f"\n如果 x=0:")
print(f"  缺口 = {0.95 * c.Q - delivered_so_far['HT-001']:.2f} 吨")
print(f"  目标函数 = {alpha_short} * {0.95 * c.Q - delivered_so_far['HT-001']:.2f} = {obj_at_zero:.2f}")

# 如果 x>0，比如 x=80 吨/天
test_x = 80.0
test_days = 5
test_total = test_x * test_days
# 考虑延迟分布，大部分隔日到
arrived = test_total * 0.95  # 95% 隔日到
new_delivered = delivered_so_far['HT-001'] + arrived
new_short = max(0, 0.95 * c.Q - new_delivered)
obj_at_x = alpha_short * new_short + beta_balance * abs(test_x - 80.0) * test_days  # 简化的均衡偏差

print(f"\n如果 x={test_x} 吨/天 * {test_days} 天:")
print(f"  新增到货 ≈ {arrived:.2f} 吨")
print(f"  新缺口 = {new_short:.2f} 吨")
print(f"  目标函数 ≈ {alpha_short} * {new_short:.2f} + 均衡偏差 = {obj_at_x:.2f}")

print(f"\n  差值 = {obj_at_zero - obj_at_x:.2f}")
if obj_at_zero - obj_at_x > 0:
    print(f"  → x>0 更优！模型可能有问题")
else:
    print(f"  → x=0 确实更优，需要调整权重")

print(f"\n{'='*80}\n")
