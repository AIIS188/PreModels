"""
complex_system_v2.py

复杂系统（Rolling Horizon LP）——多日 cap + 在途报单预测 + 延迟分布 + 估重画像 + 采购价（第三优先级软目标）

核心思想：
- 规划窗口 [today, today+H-1] 的每日发货吨 x[w,cid,k,t]
- 多日 cap 约束：sum_c x[w,cid,k,t] <= cap_forecast[w,k,t]
- 在途报单：按延迟分布分摊到未来到货日，得到 pred_mu[cid,d] / pred_hi[cid,d]
- 新增发货：同样按延迟分布映射到到货日，得到 A_new[cid,d]
- 总预计到货：Arr_total[cid,d] = pred_mu[cid,d] + A_new[cid,d]
- 目标（从高到低）：
  1) 最小化缺口 short（优先完成合同）✅
  2) 最小化到货均衡偏差 |Arr_total - q_star| ✅
  3) 最小化过期浪费期望（到货日>end_day 的新增期望）
  4) 最小化采购成本（第三优先级软目标：eta_cost 很小）
  5) 可选：计划稳定性（减少明后天抖动）

输出：
- 今天执行：x_today_plan[(w,cid,k,today)] = 吨
- 窗口计划：x_horizon_plan[(w,cid,k,day)] = 吨
- 到货诊断：arrival_plan[(cid,day)] = 期望总到货（在途 + 新增）
- 建议车数（今天）：ceil(吨 / mu_lane)，支持混装
"""

from __future__ import annotations
from typing import Dict, List, Tuple, Optional
try:
    import pulp
except ImportError as e:
    raise ImportError(
        "缺少依赖 pulp。请先安装：pip install pulp （或在你的运行环境中启用该库）"
    ) from e

from common_utils_v2 import (
    Contract, CapForecast, Delivered, WeightProfile, DelayProfile, InTransitOrders,
    default_global_delay_pmf, get_delay_dist,
    predict_intransit_arrivals_expected, suggest_trucks_from_tons_plan, get_mixing_details,
    calc_purchase_price_per_ton
)


def solve_lp_rolling_H_days(
    warehouses: List[str],
    categories: List[str],
    today: int,
    H: int,
    contracts: List[Contract],
    cap_forecast: CapForecast,
    delivered_so_far: Delivered,
    in_transit_orders: InTransitOrders,
    weight_profile: WeightProfile,

    # ========= 采购价参数（第三优先级软目标）=========
    contract_unit_price: Dict[str, float] | None = None,  # cid -> 合同含票单价（元/吨，旧版兼容）
    contract_unit_price_by_category: Dict[Tuple[str, str], float] | None = None,  # (cid, category) -> 含票单价
    warehouse_const: Dict[str, float] | None = None,      # warehouse -> 常数项（元/吨），特定仓库 +10
    invoice_factor: float = 1.048,                        # 票点
    eta_cost: float = 0.0,                                # 成本权重（建议很小，如 0.01~1）

    delay_profile: Optional[DelayProfile] = None,
    global_delay_pmf: Optional[Dict[int, float]] = None,
    rho_intransit: float = 0.9,
    alpha_short: float = 3000.0,                          # 缺口惩罚权重（最高优先级）
    beta_balance: float = 2.0,                            # 均衡偏差权重
    gamma_waste: float = 80.0,                            # 过期浪费权重
    max_daily_ratio: float = 1.5,                         # 每日到货上限（日均的倍数，默认 150%）
    default_mu_hi: Tuple[float, float] = (32.0, 35.0),
    x_prev: Optional[Dict[Tuple[str, str, str, int], float]] = None,
    stability_weight: float = 0.0,
) -> Tuple[
    Dict[Tuple[str, str, str, int], float],  # x_today_plan
    Dict[Tuple[str, str, str, int], float],  # x_horizon_plan
    Dict[Tuple[str, int], float],            # arrival_plan
    Dict[Tuple[str, str, int], int],         # truck_suggest_today (支持混装)
    Dict[Tuple[str, str, int], Dict[str, float]],  # mixing_details_today
]:
    """
    返回：
      x_today_plan[(w,cid,k,today)] = 吨
      x_horizon_plan[(w,cid,k,day)] = 吨
      arrival_plan[(cid,day)] = 期望总到货（在途 + 新增）
      truck_suggest_today[(w,cid,today)] = 建议车数（支持混装）
      mixing_details_today[(w,cid,today)] = {category: tons} 品类分配明细
    """
    if global_delay_pmf is None:
        global_delay_pmf = default_global_delay_pmf()
    if contract_unit_price is None:
        contract_unit_price = {}
    if warehouse_const is None:
        warehouse_const = {}
    if contract_unit_price_by_category is None:
        contract_unit_price_by_category = {}

    # 1) 在途预测（期望与偏重上界）
    pred_mu, pred_hi = predict_intransit_arrivals_expected(
        contracts=contracts,
        in_transit_orders=in_transit_orders,
        weight_profile=weight_profile,
        delay_profile=delay_profile,
        global_delay_pmf=global_delay_pmf,
        default_mu_hi=default_mu_hi,
    )

    # 2) 发货日窗口
    ship_days = list(range(today, today + H))

    # 3) 到货日集合（覆盖窗口发货 + 最大 delta + 合同有效期）
    max_delta = max(global_delay_pmf.keys()) if global_delay_pmf else 3
    arrival_days_set = set()
    for t in ship_days:
        for d in range(t, t + max_delta + 1):
            arrival_days_set.add(d)
    for c in contracts:
        for d in range(c.start_day, c.end_day + 1):
            arrival_days_set.add(d)
    arrival_days = sorted(arrival_days_set)

    # 4) 建模
    model = pulp.LpProblem("RollingH_LP_ArrivalBalance", pulp.LpMinimize)

    # 决策变量 x[w,cid,k,t]
    x: Dict[Tuple[str, str, str, int], pulp.LpVariable] = {}
    for w in warehouses:
        for c in contracts:
            for k in categories:
                if k not in c.allowed_categories:
                    continue
                for t in ship_days:
                    x[(w, c.cid, k, t)] = pulp.LpVariable(
                        f"x_{w}_{c.cid}_{k}_{t}", lowBound=0, cat="Continuous"
                    )

    # 5) 能力约束：多日 cap
    for w in warehouses:
        for k in categories:
            for t in ship_days:
                cap = float(cap_forecast.get((w, k, t), 0.0))
                expr = []
                for c in contracts:
                    key = (w, c.cid, k, t)
                    if key in x:
                        expr.append(x[key])
                if expr:
                    model += (pulp.lpSum(expr) <= cap, f"Cap_{w}_{k}_{t}")

    # 6) 新增发货映射到到货日 A_new[cid,d]
    A_new: Dict[Tuple[str, int], pulp.LpAffineExpression] = {}
    waste_exp: Dict[str, pulp.LpAffineExpression] = {}

    for c in contracts:
        waste_terms = []
        for d in arrival_days:
            expr_terms = []
            for t in ship_days:
                delta = d - t
                if delta < 0:
                    continue
                for w in warehouses:
                    dist = get_delay_dist(w, c.receiver, delay_profile=delay_profile, global_delay_pmf=global_delay_pmf)
                    p = float(dist.get(delta, 0.0))
                    if p <= 0:
                        continue
                    for k in categories:
                        key = (w, c.cid, k, t)
                        if key in x:
                            expr_terms.append(x[key] * p)
            if expr_terms:
                A_new[(c.cid, d)] = pulp.lpSum(expr_terms)
                if d > c.end_day:
                    waste_terms.append(A_new[(c.cid, d)])
        waste_exp[c.cid] = pulp.lpSum(waste_terms) if waste_terms else 0

    # 7) 缺口与均衡偏差
    short: Dict[str, pulp.LpVariable] = {}
    dev_pos: Dict[Tuple[str, int], pulp.LpVariable] = {}
    dev_neg: Dict[Tuple[str, int], pulp.LpVariable] = {}

    for c in contracts:
        cid = c.cid
        delivered = float(delivered_so_far.get(cid, 0.0))

        remain_start = max(today, c.start_day)
        if remain_start > c.end_day:
            continue

        T = c.end_day - remain_start + 1
        if T <= 0:
            continue

        # 在途预测（有效期内）：只计算今天及以后到达的
        future_intransit_mu = 0.0
        future_intransit_hi = 0.0
        for d in range(today + 1, c.end_day + 1):
            future_intransit_mu += float(pred_mu.get((cid, d), 0.0))
            future_intransit_hi += float(pred_hi.get((cid, d), 0.0))

        # 新增发货（有效期内）期望：从今天开始算
        add_valid_terms = []
        for d in range(today, c.end_day + 1):
            expr = A_new.get((cid, d), None)
            if expr is not None:
                add_valid_terms.append(expr)
        add_valid_expr = pulp.lpSum(add_valid_terms) if add_valid_terms else 0

        # q_star: 均衡到货目标（考虑在途和已到货）
        # ✅ 优化：q_star = (0.95*Q - delivered - future_intransit) / T + 已有在途的日均
        # 这样均衡目标更合理，不会为了均衡而少发货
        R = max(0.0, 0.95 * c.Q - delivered - rho_intransit * future_intransit_mu)
        target_daily = R / T
        # q_star 包含已有在途的日均贡献
        q_star = target_daily + (rho_intransit * future_intransit_mu) / T

        # 缺口（允许±5% 冗余）
        short[cid] = pulp.LpVariable(f"short_{cid}", lowBound=0)
        expected_total = delivered + future_intransit_mu + add_valid_expr
        # ✅ 目标：至少完成 95% 合同量
        model += (short[cid] >= 0.95 * c.Q - expected_total, f"ShortDef_{cid}")

        # 超发硬约束（保守：在途用 hi，允许 105%）
        model += (delivered + future_intransit_hi + add_valid_expr <= 1.05 * c.Q, f"OverCap_{cid}")

        # 到货均衡（有效期内每一天，从今天开始算）
        # ✅ 优化：只均衡新增发货，不包含在途（在途已固定）
        for d in range(today, c.end_day + 1):
            add_expr = A_new.get((cid, d), 0)
            dev_pos[(cid, d)] = pulp.LpVariable(f"dev_pos_{cid}_{d}", lowBound=0)
            dev_neg[(cid, d)] = pulp.LpVariable(f"dev_neg_{cid}_{d}", lowBound=0)
            model += (add_expr - target_daily == dev_pos[(cid, d)] - dev_neg[(cid, d)], f"Balance_{cid}_{d}")

        # ✅ 新增：每日到货上限约束（防止集中到货）
        max_daily_arrival = target_daily * max_daily_ratio
        for d in range(today, c.end_day + 1):
            # 在途 + 新增的总到货
            pred_d = float(pred_mu.get((cid, d), 0.0))
            add_expr = A_new.get((cid, d), 0)
            model += (pred_d + add_expr <= max_daily_arrival, f"MaxDaily_{cid}_{d}")

    # 8) 计划稳定性（可选）
    stab_terms = []
    if stability_weight > 0 and x_prev is not None:
        for key, var in x.items():
            w, cid, k, t = key
            if t <= today:
                continue
            prev_val = float(x_prev.get((w, cid, k, t), 0.0))
            u = pulp.LpVariable(f"stab_{w}_{cid}_{k}_{t}", lowBound=0)
            model += (u >= var - prev_val, f"StabPos_{w}_{cid}_{k}_{t}")
            model += (u >= prev_val - var, f"StabNeg_{w}_{cid}_{k}_{t}")
            stab_terms.append(u)

    # 9) 目标函数
    obj_short = pulp.lpSum(short.values()) if short else 0
    obj_balance = (pulp.lpSum(dev_pos.values()) + pulp.lpSum(dev_neg.values())) if dev_pos else 0
    obj_waste = pulp.lpSum(waste_exp.values()) if waste_exp else 0
    obj_stab = pulp.lpSum(stab_terms) if stab_terms else 0

    # 采购成本（第三优先级软目标）
    def get_price(w: str, cid: str, k: str) -> float:
        """获取采购单价（支持品类单价 + 仓库加价）"""
        # 优先使用品类单价
        unit_price = contract_unit_price_by_category.get((cid, k), contract_unit_price.get(cid, 0.0))
        const = float(warehouse_const.get(w, 0.0))
        return calc_purchase_price_per_ton(unit_price, invoice_factor=invoice_factor, const=const)

    obj_cost = pulp.lpSum(
        var * get_price(w, cid, k)
        for (w, cid, k, t), var in x.items()
    ) if eta_cost and eta_cost > 0 else 0

    model += (
        alpha_short * obj_short
        + beta_balance * obj_balance
        + gamma_waste * obj_waste
        + stability_weight * obj_stab
        + eta_cost * obj_cost
    )

    # 求解
    model.solve(pulp.PULP_CBC_CMD(msg=False))

    # 10) 输出
    x_horizon_plan: Dict[Tuple[str, str, str, int], float] = {}
    for key, var in x.items():
        val = var.value()
        if val and val > 1e-6:
            x_horizon_plan[key] = float(val)

    x_today_plan = {k: v for k, v in x_horizon_plan.items() if k[3] == today}

    # 到货诊断（有效期内）
    arrival_plan: Dict[Tuple[str, int], float] = {}
    for c in contracts:
        cid = c.cid
        for d in range(max(today, c.start_day), c.end_day + 1):
            pred = float(pred_mu.get((cid, d), 0.0))
            add_expr = A_new.get((cid, d), None)
            add_val = float(add_expr.value()) if add_expr is not None else 0.0
            total = pred + add_val
            if total > 1e-6:
                arrival_plan[(cid, d)] = total

    # 车数建议（今天，支持混装）
    truck_suggest_today = suggest_trucks_from_tons_plan(
        tons_plan=x_today_plan,
        contracts=contracts,
        weight_profile=weight_profile,
        default_mu_hi=default_mu_hi,
        allow_mixing=True,  # 启用混装模式
    )

    # 混装明细（用于指导实际装车）
    mixing_details_today = get_mixing_details(
        tons_plan=x_today_plan,
        contracts=contracts,
        weight_profile=weight_profile,
        default_mu_hi=default_mu_hi,
    )

    return x_today_plan, x_horizon_plan, arrival_plan, truck_suggest_today, mixing_details_today
