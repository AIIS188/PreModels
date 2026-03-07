"""
simple_system_v2.py

简单系统（Baseline）——单日 cap + 在途期望 + 临期优先贪心

核心思想：
1) 对每个合同 c：
   - 剩余需求 = Q - (已到货 + rho * 在途期望到货)
   - 剩余有效到货天数 T_remain
   - 当日目标吨：target_c = max(0, 剩余需求 / T_remain)

2) 用当天 cap_today[w,k] 贪心分配：
   - 合同排序：临期优先（end_day 近优先），缺口大次优先
   - 仓库排序：准时概率高优先，其次 cap 大优先
   - ✅ 合同只认总重：品类在允许范围内自由分配，总重达标即可

说明：
- 不需要求解器（不依赖 pulp）
- 仅用当天 cap，不考虑未来 cap
- ✅ 支持混装：同一 (warehouse, cid, day) 的不同品类可以拼车
"""

from __future__ import annotations
from typing import Dict, List, Tuple
import copy

from common_utils_v2 import (
    Contract, CapToday, Delivered, WeightProfile, DelayProfile, InTransitOrders,
    default_global_delay_pmf, get_delay_dist,
    predict_intransit_arrivals_expected, intransit_total_expected_in_valid_window,
    suggest_trucks_from_tons_plan, get_mixing_details, calc_purchase_price_per_ton
)


def simple_daily_planner(
    warehouses: List[str],
    categories: List[str],
    today: int,
    contracts: List[Contract],
    cap_today: CapToday,
    delivered_so_far: Delivered,
    in_transit_orders: InTransitOrders,
    weight_profile: WeightProfile,

    # ========= 参数（第三优先级软目标，暂时无用）=========
    contract_unit_price: Dict[str, float] | None = None,
    warehouse_const: Dict[str, float] | None = None,
    invoice_factor: float = 1.048,

    delay_profile: DelayProfile | None = None,
    global_delay_pmf: Dict[int, float] | None = None,
    rho_intransit: float = 0.9,
    default_mu_hi: Tuple[float, float] = (32.0, 35.0),
) -> Tuple[Dict[Tuple[str, str, str, int], float], Dict[Tuple[str, int], float], Dict[Tuple[str, str, int], int], Dict[Tuple[str, str, int], Dict[str, float]]]:
    """
    返回：
      x_plan_today[(w,cid,k,today)] = 吨
      arrival_diag[(cid, day)] = 期望到货吨（在途期望 + 今日新增期望），用于诊断
      truck_suggest[(w,cid,today)] = 建议车数（支持混装，按 lane 聚合）
      mixing_details[(w,cid,today)] = {category: tons} 每车的品类分配明细
    """
    if global_delay_pmf is None:
        global_delay_pmf = default_global_delay_pmf()

    # 1) 在途预测（期望到货）
    pred_mu, _pred_hi = predict_intransit_arrivals_expected(
        contracts=contracts,
        in_transit_orders=in_transit_orders,
        weight_profile=weight_profile,
        delay_profile=delay_profile,
        global_delay_pmf=global_delay_pmf,
        default_mu_hi=default_mu_hi,
    )

    # 2) 计算每个合同的当日目标 target_c（总重，不区分品类）
    contract_targets: Dict[str, float] = {}
    for c in contracts:
        remain_start = max(today, c.start_day)  # 剩余发货日从今日开始
        
        if remain_start > c.end_day:
            contract_targets[c.cid] = 0.0
            continue

        T_remain = c.end_day - remain_start + 1
        delivered = float(delivered_so_far.get(c.cid, 0.0))
        
        # ✅ 修复：在途期望只计算今天及以后到达的（今天到达的不算，因为今天快结束了）
        intransit_mu_valid = intransit_total_expected_in_valid_window(
            c.cid, pred_mu, today + 1, c.end_day
        )
        
        h = delivered + rho_intransit * intransit_mu_valid
        remaining = max(0.0, c.Q - h)
        target = remaining / T_remain
        
        # ✅ 优化：设置最小发货量（避免太少无法装车）
        contract_targets[c.cid] = max(target, 32.0)  # 至少 1 车

    # 3) 合同优先级：临期优先（越临期越优先）
    def urgency_key(c: Contract) -> Tuple[int, float]:
        days_left = max(0, c.end_day - today)
        return (days_left, -contract_targets.get(c.cid, 0.0))

    contracts_sorted = sorted(contracts, key=urgency_key)

    # 4) cap 剩余
    cap_rem = copy.deepcopy(cap_today)

    # 5) 分配发货：x_today[(w,cid,k,today)]
    # ✅ 修改：合同只认总重，品类自由分配
    x_today: Dict[Tuple[str, str, str, int], float] = {}

    # 工具：计算某仓->该合同收货方 "到期内到达概率"
    def p_on_time(w: str, receiver: str, end_day: int) -> float:
        dist = get_delay_dist(w, receiver, delay_profile=delay_profile, global_delay_pmf=global_delay_pmf)
        prob = 0.0
        for delta, p in dist.items():
            if today + int(delta) <= end_day:
                prob += float(p)
        return prob

    for c in contracts_sorted:
        need = float(contract_targets.get(c.cid, 0.0))
        if need <= 1e-6:
            continue

        days_left = max(0, c.end_day - today)

        # ✅ 优化：多轮分配，直到需求满足或无可用产能
        while need > 1e-6:
            # 每轮重新构建可用 (warehouse, category) 组合
            wh_k_rank = []
            for w in warehouses:
                for k in categories:
                    if k not in c.allowed_categories:
                        continue
                    
                    cap_wk = float(cap_rem.get((w, k), 0.0))
                    if cap_wk <= 1e-6:
                        continue
                    
                    p = p_on_time(w, c.receiver, c.end_day)
                    # 临期时过滤掉准时率低的
                    if days_left <= 2 and p < 0.9:
                        continue
                    
                    wh_k_rank.append((w, k, p, cap_wk))

            if not wh_k_rank:
                break  # 无可用产能

            # 排序：准时概率高优先，其次 cap 大优先
            wh_k_rank.sort(key=lambda x: (-x[2], -x[3]))

            # 从优先级最高的组合分配
            (w, k, p, cap_wk) = wh_k_rank[0]
            alloc = min(need, cap_wk)
            
            if alloc <= 1e-9:
                break
            
            x_today[(w, c.cid, k, today)] = x_today.get((w, c.cid, k, today), 0.0) + alloc
            cap_rem[(w, k)] = cap_wk - alloc
            need -= alloc

    # 6) 到货诊断：在途期望 + 今日新增期望
    arrival_diag: Dict[Tuple[str, int], float] = {}
    for (cid, d), qty in pred_mu.items():
        if qty > 1e-9:
            arrival_diag[(cid, d)] = arrival_diag.get((cid, d), 0.0) + float(qty)

    for (w, cid, k, t), tons in x_today.items():
        c = next(cc for cc in contracts if cc.cid == cid)
        dist = get_delay_dist(w, c.receiver, delay_profile=delay_profile, global_delay_pmf=global_delay_pmf)
        for delta, p in dist.items():
            d = today + int(delta)
            arrival_diag[(cid, d)] = arrival_diag.get((cid, d), 0.0) + float(tons) * float(p)

    # 7) 车数建议（支持混装）
    truck_suggest = suggest_trucks_from_tons_plan(
        tons_plan=x_today,
        contracts=contracts,
        weight_profile=weight_profile,
        default_mu_hi=default_mu_hi,
        allow_mixing=True,  # 启用混装模式
    )

    # 8) 混装明细（用于指导实际装车）
    mixing_details = get_mixing_details(
        tons_plan=x_today,
        contracts=contracts,
        weight_profile=weight_profile,
        default_mu_hi=default_mu_hi,
    )

    return x_today, arrival_diag, truck_suggest, mixing_details
