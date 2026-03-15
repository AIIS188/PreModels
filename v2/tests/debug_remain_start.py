"""
debug_remain_start.py

调试 remain_start 计算，看是否导致约束被跳过
"""

from core.date_utils import DateUtils

c_start = "2026-03-01"
c_end = "2026-03-25"
today = "2026-03-15"

# complex_system_v2.py 中的逻辑
remain_start = today if DateUtils.diff_days(today, c_start) > 0 else c_start

print("=" * 80)
print("remain_start 分析")
print("=" * 80)

print(f"\n合同有效期：{c_start} 到 {c_end}")
print(f"今天：{today}")
print(f"diff_days(today, c_start) = {DateUtils.diff_days(today, c_start)}")
print(f"remain_start = {remain_start}")

T = DateUtils.diff_days(remain_start, c_end) + 1
print(f"\n剩余天数 T = {T}")

if T <= 0:
    print("⚠️  T <= 0，约束会被跳过！")
else:
    print("✅ T > 0，约束会添加")

print(f"\n{'='*80}\n")
