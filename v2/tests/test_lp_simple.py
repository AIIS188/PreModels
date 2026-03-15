"""
test_lp_simple.py

最简单的 LP 测试，验证 PuLP 能否正常工作
"""

import pulp

# 创建模型
model = pulp.LpProblem("SimpleTest", pulp.LpMinimize)

# 变量
x = pulp.LpVariable('x', lowBound=0)
y = pulp.LpVariable('y', lowBound=0)

# 约束
model += (x + y <= 100, "capacity")
model += (x >= 10, "min_x")

# 目标
model += x + y

# 求解
model.solve(pulp.PULP_CBC_CMD(msg=0))

print(f"Status: {pulp.LpStatus[model.status]}")
print(f"x = {x.value()}")
print(f"y = {y.value()}")
print(f"obj = {pulp.value(model.objective)}")
