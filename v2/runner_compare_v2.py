"""
runner_compare_v2.py

用途：
- 用同一份输入数据同时运行：
  1) 简单系统（simple_system_v2.simple_daily_planner）
  2) 复杂系统（complex_system_v2.solve_lp_rolling_H_days）
- 打印"今天发货吨 + 建议车数"（支持混装）
- 打印每个合同未来到货曲线（期望）
- 计算对比指标：峰值、均值、标准差、缺口（期望）、过期浪费期望
- 计算采购成本对比（元）：按仓库常数项 +10 的规则（第三优先级软目标）

运行方式：
    python runner_compare_v2.py
"""

from __future__ import annotations
from typing import Dict, Tuple, List
import math
from collections import defaultdict

from common_utils_v2 import (
    Contract, default_global_delay_pmf, get_delay_dist,
    predict_intransit_arrivals_expected, calc_purchase_price_per_ton
)

from simple_system_v2 import simple_daily_planner
from complex_system_v2 import solve_lp_rolling_H_days


def _compute_expected_arrivals_from_plan(
    plan_tons: Dict[Tuple[str, str, str, int], float],
    contracts: List[Contract],
    delay_profile: Dict[Tuple[str, str], Dict[int, float]] | None,
    global_delay_pmf: Dict[int, float],
) -> Dict[Tuple[str, int], float]:
    """将吨级发货计划按延迟分布映射为未来到货期望（按合同 - 到货日）"""
    receiver_by_cid = {c.cid: c.receiver for c in contracts}
    arr: Dict[Tuple[str, int], float] = {}
    for (w, cid, k, t), tons in plan_tons.items():
        receiver = receiver_by_cid[cid]
        dist = get_delay_dist(w, receiver, delay_profile=delay_profile, global_delay_pmf=global_delay_pmf)
        for delta, p in dist.items():
            d = t + int(delta)
            arr[(cid, d)] = arr.get((cid, d), 0.0) + float(tons) * float(p)
    return arr


def _metrics_per_contract(
    cid: str,
    c: Contract,
    today: int,
    delivered_so_far: Dict[str, float],
    pred_mu: Dict[Tuple[str, int], float],
    add_mu: Dict[Tuple[str, int], float],
) -> Dict[str, float]:
    """指标（期望口径）：均值/峰值/std + 期望缺口 + 新增过期浪费"""
    delivered = float(delivered_so_far.get(cid, 0.0))
    remain_start = max(today + 1, c.start_day)
    if remain_start > c.end_day:
        series = []
    else:
        series = [float(pred_mu.get((cid, d), 0.0)) + float(add_mu.get((cid, d), 0.0))
                  for d in range(remain_start, c.end_day + 1)]

    if not series:
        mean = peak = std = 0.0
    else:
        mean = sum(series) / len(series)
        peak = max(series)
        var = sum((x - mean) ** 2 for x in series) / len(series)
        std = math.sqrt(var)

    valid_total = sum(series) if series else 0.0
    expected_total_delivered = delivered + valid_total
    short = max(0.0, c.Q - expected_total_delivered)

    waste = 0.0
    for (ccid, d), qty in add_mu.items():
        if ccid == cid and d > c.end_day:
            waste += float(qty)

    return {"mean": mean, "peak": peak, "std": std, "short": short, "waste": waste, "days": float(len(series))}


def _compute_purchase_cost(
    plan_tons: Dict[Tuple[str, str, str, int], float],
    contract_unit_price: Dict[str, float],
    warehouse_const: Dict[str, float],
    invoice_factor: float = 1.048,
) -> float:
    """计算吨计划的采购成本（元）"""
    total = 0.0
    for (w, cid, k, t), tons in plan_tons.items():
        unit = float(contract_unit_price.get(cid, 0.0))
        const = float(warehouse_const.get(w, 0.0))
        price = calc_purchase_price_per_ton(unit, invoice_factor=invoice_factor, const=const)
        total += float(tons) * float(price)
    return total


def main():
    # =========================
    # 示例数据（你可替换为真实数据）
    # =========================
    warehouses = ["W1", "W2", "W3"]
    categories = ["A", "B"]
    today = 10

    contracts = [
        Contract(cid="C1", receiver="R1", Q=520.0, start_day=9, end_day=13, allowed_categories={"A", "B"}),
        Contract(cid="C2", receiver="R2", Q=900.0, start_day=8, end_day=20, allowed_categories={"A", "B"}),
    ]

    delivered_so_far = {"C1": 120.0, "C2": 520.0}

    cap_today = {
        ("W1", "A"): 220.0, ("W1", "B"): 60.0,
        ("W2", "A"): 80.0,  ("W2", "B"): 220.0,
        ("W3", "A"): 120.0, ("W3", "B"): 120.0,
    }

    # 多日 cap 预测（示例）：当天 cap + 波动
    H = 10
    cap_forecast = {}
    for t in range(today, today + H):
        for (w, k), base in cap_today.items():
            factor = 1.05 if (t % 2 == 0) else 0.90
            cap_forecast[(w, k, t)] = float(base) * factor

    # 估重画像（示例）
    weight_profile = {
        ("W1", "R1", "A"): (32.0, 35.0), ("W1", "R1", "B"): (30.0, 35.0),
        ("W2", "R1", "A"): (31.0, 35.0), ("W2", "R1", "B"): (33.0, 35.0),
        ("W3", "R1", "A"): (29.0, 35.0), ("W3", "R1", "B"): (28.0, 35.0),
        ("W1", "R2", "A"): (33.0, 35.0), ("W1", "R2", "B"): (32.0, 35.0),
        ("W2", "R2", "A"): (30.0, 35.0), ("W2", "R2", "B"): (31.0, 35.0),
        ("W3", "R2", "A"): (28.0, 35.0), ("W3", "R2", "B"): (29.0, 35.0),
    }

    # 延迟分布（示例）
    delay_profile = {
        ("W1", "R1"): {0: 0.03, 1: 0.90, 2: 0.04, 3: 0.03},
        ("W2", "R1"): {0: 0.02, 1: 0.92, 2: 0.04, 3: 0.02},
        ("W3", "R1"): {0: 0.05, 1: 0.85, 2: 0.06, 3: 0.04},
        ("W1", "R2"): {0: 0.02, 1: 0.90, 2: 0.05, 3: 0.03},
        ("W2", "R2"): {0: 0.03, 1: 0.88, 2: 0.06, 3: 0.03},
        ("W3", "R2"): {0: 0.04, 1: 0.86, 2: 0.06, 3: 0.04},
    }

    global_delay = default_global_delay_pmf()

    # 在途报单（示例）
    in_transit_orders = [
        {"order_id": "O1001", "cid": "C1", "receiver": "R1", "warehouse": "W1", "category": "A", "ship_day": 9},
        {"order_id": "O1002", "cid": "C1", "receiver": "R1", "warehouse": "W2", "category": "B", "ship_day": 9},
        {"order_id": "O2001", "cid": "C2", "receiver": "R2", "warehouse": "W1", "category": "A", "ship_day": 9},
        {"order_id": "O2002", "cid": "C2", "receiver": "R2", "warehouse": "W1", "category": "A", "ship_day": 9},
        {"order_id": "O2003", "cid": "C2", "receiver": "R2", "warehouse": "W2", "category": "B", "ship_day": 9},
        {"order_id": "O2004", "cid": "C2", "receiver": "R2", "warehouse": "W2", "category": "B", "ship_day": 9},
        {"order_id": "O2005", "cid": "C2", "receiver": "R2", "warehouse": "W3", "category": "A", "ship_day": 9},
    ]

    # 采购价输入（示例）
    contract_unit_price = {"C1": 520.0, "C2": 480.0}
    # 仓库常数项：示例 W2 为于娇娇/王菲体系（+10）
    warehouse_const = {"W1": 0.0, "W2": 10.0, "W3": 0.0}

    # 统一算在途期望（两系统共用）
    pred_mu, _pred_hi = predict_intransit_arrivals_expected(
        contracts=contracts,
        in_transit_orders=in_transit_orders,
        weight_profile=weight_profile,
        delay_profile=delay_profile,
        global_delay_pmf=global_delay,
        default_mu_hi=(32.0, 35.0),
    )

    # =========================
    # 运行简单系统
    # =========================
    simple_x_today, _simple_arrival_diag, simple_trucks, simple_mixing = simple_daily_planner(
        warehouses=warehouses,
        categories=categories,
        today=today,
        contracts=contracts,
        cap_today=cap_today,
        delivered_so_far=delivered_so_far,
        in_transit_orders=in_transit_orders,
        weight_profile=weight_profile,
        contract_unit_price=contract_unit_price,
        warehouse_const=warehouse_const,
        invoice_factor=1.048,
        delay_profile=delay_profile,
        global_delay_pmf=global_delay,
        rho_intransit=0.9,
        default_mu_hi=(32.0, 35.0),
    )
    simple_add_mu = _compute_expected_arrivals_from_plan(simple_x_today, contracts, delay_profile, global_delay)

    # =========================
    # 运行复杂系统（多日 cap 滚动 LP）
    # =========================
    complex_x_today, complex_x_horizon, _complex_arrival, complex_trucks, complex_mixing = solve_lp_rolling_H_days(
        warehouses=warehouses,
        categories=categories,
        today=today,
        H=H,
        contracts=contracts,
        cap_forecast=cap_forecast,
        delivered_so_far=delivered_so_far,
        in_transit_orders=in_transit_orders,
        weight_profile=weight_profile,
        contract_unit_price=contract_unit_price,
        warehouse_const=warehouse_const,
        invoice_factor=1.048,
        eta_cost=0.2,
        delay_profile=delay_profile,
        global_delay_pmf=global_delay,
        rho_intransit=0.9,
        alpha_short=3000.0,
        beta_balance=2.0,
        gamma_waste=80.0,
        default_mu_hi=(32.0, 35.0),
        x_prev=None,
        stability_weight=0.0,
    )
    complex_add_mu = _compute_expected_arrivals_from_plan(complex_x_horizon, contracts, delay_profile, global_delay)

    # =========================
    # 打印：今日计划（吨 + 车）
    # =========================
    def print_today(name: str, plan, trucks, mixing=None):
        print(f"\n==================== {name}：今日发货计划（吨 + 车数） ====================")
        if not plan:
            print("(空)")
            return

        # 按 (w, cid, t) 聚合打印（支持混装）
        plan_grouped: Dict[Tuple[str, str, int], Dict[str, float]] = defaultdict(dict)
        for (w, cid, k, t), tons in sorted(plan.items()):
            plan_grouped[(w, cid, t)][k] = tons

        for (w, cid, t), cats in plan_grouped.items():
            total_tons = sum(cats.values())
            truck_key = (w, cid, t)
            trucks_count = trucks.get(truck_key, 0)

            # 打印品类明细
            cats_str = ", ".join(f"{k}={v:.1f}吨" for k, v in sorted(cats.items()))
            print(f"day={t}  仓={w}  合同={cid}  总吨={total_tons:.1f}  建议车数={trucks_count}  品类明细=[{cats_str}]")

            # 打印混装明细（如果有）
            if mixing and truck_key in mixing:
                mix = mixing[truck_key]
                mix_str = ", ".join(f"{k}={v:.1f}" for k, v in sorted(mix.items()))
                print(f"         └─ 混装建议：{mix_str}")

    print_today("简单系统", simple_x_today, simple_trucks, simple_mixing)
    print_today("复杂系统", complex_x_today, complex_trucks, complex_mixing)

    # =========================
    # 采购成本对比（元）
    # =========================
    simple_cost = _compute_purchase_cost(simple_x_today, contract_unit_price, warehouse_const, invoice_factor=1.048)
    complex_cost_today = _compute_purchase_cost(complex_x_today, contract_unit_price, warehouse_const, invoice_factor=1.048)
    complex_cost_horizon = _compute_purchase_cost(complex_x_horizon, contract_unit_price, warehouse_const, invoice_factor=1.048)

    print("\n==================== 采购成本对比（元） ====================")
    print(f"简单系统 今日计划采购成本：{simple_cost:,.0f} 元")
    print(f"复杂系统 今日计划采购成本：{complex_cost_today:,.0f} 元")
    print(f"复杂系统 窗口计划采购成本 (诊断): {complex_cost_horizon:,.0f} 元")

    # =========================
    # 未来到货曲线（期望）
    # =========================
    def print_arrivals(name: str, add_mu: Dict[Tuple[str, int], float], horizon_days: int = 8):
        print(f"\n==================== {name}：未来到货曲线（期望=在途 + 新增） ====================")
        for c in contracts:
            cid = c.cid
            print(f"\n合同 {cid} 有效期 [{c.start_day},{c.end_day}]：")
            start = max(today + 1, c.start_day)
            end = min(c.end_day, today + horizon_days)
            for d in range(start, end + 1):
                total = float(pred_mu.get((cid, d), 0.0)) + float(add_mu.get((cid, d), 0.0))
                print(f"  到货日 {d}: {total:.1f} 吨")

    print_arrivals("简单系统", simple_add_mu)
    print_arrivals("复杂系统 (窗口计划诊断)", complex_add_mu)

    # =========================
    # 指标对比（期望口径）
    # =========================
    print("\n==================== 指标对比（期望口径） ====================")
    header = f"{'系统':<14} {'合同':<4} {'均值':>8} {'峰值':>8} {'Std':>8} {'缺口':>10} {'浪费':>10} {'天数':>6}"
    print(header)
    print("-" * len(header))

    for sys_name, add_mu in [("简单系统", simple_add_mu), ("复杂系统", complex_add_mu)]:
        for c in contracts:
            m = _metrics_per_contract(c.cid, c, today, delivered_so_far, pred_mu, add_mu)
            print(f"{sys_name:<14} {c.cid:<4} {m['mean']:>8.1f} {m['peak']:>8.1f} {m['std']:>8.1f} {m['short']:>10.1f} {m['waste']:>10.1f} {int(m['days']):>6d}")

    # =========================
    # 混装效果对比
    # =========================
    print("\n==================== 混装效果对比 ====================")

    def count_trucks(trucks, mixing):
        total = sum(trucks.values())
        # 计算如果不禁混装需要的车数（按品类分开）
        return total

    simple_trucks_total = count_trucks(simple_trucks, simple_mixing)
    complex_trucks_total = count_trucks(complex_trucks, complex_mixing)

    print(f"简单系统 总车数：{simple_trucks_total} 车（混装模式）")
    print(f"复杂系统 总车数：{complex_trucks_total} 车（混装模式）")
    print("\n备注：")
    print("1) 复杂系统的到货曲线这里使用'窗口内全计划'做诊断；实际执行只做今天，明天会重算。")
    print("2) '浪费'这里只统计新增计划导致的有效期外到货期望（不含在途已发造成的过期）。")
    print("3) 想更贴近执行：可把复杂系统 add_mu 改成只用 today 的计划（complex_x_today）。")
    print("4) ✅ 混装模式：同一 (warehouse, cid, day) 的不同品类可以拼车，减少总车数。")


if __name__ == "__main__":
    main()
