"""
debug_a_new_keys.py

调试 A_new 的键，看是否与查询匹配
"""

import sys
from pathlib import Path
import pulp

v2_dir = Path(__file__).parent.parent
if str(v2_dir) not in sys.path:
    sys.path.insert(0, str(v2_dir))

from models.common_utils_v2 import Contract, default_global_delay_pmf, get_delay_dist
from core.date_utils import DateUtils

c = Contract(cid="HT-001", receiver="R1", Q=1000.0, start_day="2026-03-01", end_day="2026-03-25", products=[{"product_name": "A", "unit_price": 800.0}])

today = "2026-03-15"
H = 10
warehouses = ["W1"]
categories = ["A"]
ship_days = [DateUtils.add_days(today, d) for d in range(H)]

# 到货日集合
max_delta = max(default_global_delay_pmf().keys())
arrival_days_set = set()
for t in ship_days:
    for d in range(max_delta + 1):
        arrival_days_set.add(DateUtils.add_days(t, d))

date = c.start_day
while DateUtils.diff_days(date, c.end_day) >= 0:
    arrival_days_set.add(date)
    date = DateUtils.add_days(date, 1)

arrival_days = sorted(arrival_days_set)

# 创建变量
x = {}
for w in warehouses:
    for k in categories:
        for t in ship_days:
            x[(w, c.cid, k, t)] = pulp.LpVariable(f"x_{w}_{c.cid}_{k}_{t.replace('-', '')}", lowBound=0)

# 构建 A_new
A_new = {}
for d in arrival_days:
    expr_terms = []
    for t in ship_days:
        delta = DateUtils.diff_days(t, d)
        if delta < 0:
            continue
        for w in warehouses:
            dist = get_delay_dist(w, c.receiver, global_delay_pmf=default_global_delay_pmf())
            p = float(dist.get(delta, 0.0))
            if p <= 0:
                continue
            for k in categories:
                key = (w, c.cid, k, t)
                if key in x:
                    expr_terms.append(x[key] * p)
    if expr_terms:
        A_new[(c.cid, d)] = pulp.lpSum(expr_terms)

print("=" * 80)
print("A_new 键分析")
print("=" * 80)

print(f"\nA_new 键：{len(A_new)} 个")
for key in list(A_new.keys())[:10]:
    print(f"  {key}")

# 查询 A_new (模拟 ShortDef 约束构建)
print(f"\n查询 A_new (从今天到合同结束):")
add_valid_terms = []
d = today
while DateUtils.diff_days(d, c.end_day) >= 0:
    expr = A_new.get((c.cid, d), None)
    if expr is not None:
        add_valid_terms.append(expr)
        print(f"  {d}: ✅ 找到")
    else:
        print(f"  {d}: ❌ 未找到")
    d = DateUtils.add_days(d, 1)

print(f"\nadd_valid_terms: {len(add_valid_terms)} 项")
print(f"add_valid_expr: {add_valid_terms}")

print(f"\n{'='*80}\n")
