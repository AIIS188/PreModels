"""
debug_waste.py

调试 waste_exp 计算，看是否抑制了发货
"""

import sys
from pathlib import Path

v2_dir = Path(__file__).parent.parent
if str(v2_dir) not in sys.path:
    sys.path.insert(0, str(v2_dir))

from models.common_utils_v2 import Contract, default_global_delay_pmf, get_delay_dist
from core.date_utils import DateUtils

c = Contract(cid="HT-001", receiver="R1", Q=1000.0, start_day="2026-03-01", end_day="2026-03-25", products=[{"product_name": "A", "unit_price": 800.0}])

today = "2026-03-15"
H = 10
ship_days = [DateUtils.add_days(today, d) for d in range(H)]

# 到货日集合
max_delta = max(default_global_delay_pmf().keys())
arrival_days_set = set()
for t in ship_days:
    for d in range(max_delta + 1):
        arrival_days_set.add(DateUtils.add_days(t, d))

# 合同有效期
date = c.start_day
while DateUtils.diff_days(date, c.end_day) >= 0:
    arrival_days_set.add(date)
    date = DateUtils.add_days(date, 1)

arrival_days = sorted(arrival_days_set)

print("=" * 80)
print("waste_exp 分析")
print("=" * 80)

print(f"\n合同有效期：{c.start_day} 到 {c.end_day}")
print(f"发货窗口：{ship_days[0]} 到 {ship_days[-1]} ({len(ship_days)} 天)")
print(f"到货日集合：{arrival_days[0]} 到 {arrival_days[-1]} ({len(arrival_days)} 天)")

# 计算哪些到货日会产生 waste
print(f"\n会产生 waste 的到货日 (d < end_day):")
waste_days = []
for d in arrival_days:
    diff = DateUtils.diff_days(d, c.end_day)
    if diff < 0:
        waste_days.append(d)
        print(f"  {d} (提前 {abs(diff)} 天)")

print(f"\nwaste_days 总数：{len(waste_days)} 天")
print(f"非 waste 的到货日：{len(arrival_days) - len(waste_days)} 天")

# 如果今天发货，多少会产生 waste？
print(f"\n如果今天 ({today}) 发货:")
for delta, p in default_global_delay_pmf().items():
    arrival_date = DateUtils.add_days(today, delta)
    is_waste = DateUtils.diff_days(arrival_date, c.end_day) < 0
    print(f"  Δ={delta} (p={p:.2f}): 到货 {arrival_date}, waste={is_waste}")

print(f"\n{'='*80}\n")
