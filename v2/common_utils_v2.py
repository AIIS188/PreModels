"""
common_utils_v2.py

通用工具模块（供 simple_system_v2.py 与 complex_system_v2.py 复用）

功能：
1) 结构体：Contract
2) 延迟分布与估重画像的读取/兜底
3) 在途报单 -> 未来到货期望（按 Δ 概率分摊）
4) “吨 -> 建议车数”换算（用均车重 mu）
5) 采购价口径：基础价*票点+常数（按仓库常数项）
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Tuple, Set, Optional
import math

# =========================
# 结构体：合同
# =========================

@dataclass(frozen=True)
class Contract:
    cid: str                      # 合同ID
    receiver: str                 # 收货方（同一收货方仅1个活跃合同）
    Q: float                      # 合同总量（吨）
    start_day: int                # 到货有效期开始（按天）
    end_day: int                  # 到货有效期结束（按天）
    allowed_categories: Set[str]  # 允许的品类集合（不混装）


# =========================
# 类型别名
# =========================

CapToday = Dict[Tuple[str, str], float]                 # cap_today[(w,k)] = 吨
CapForecast = Dict[Tuple[str, str, int], float]         # cap_forecast[(w,k,day)] = 吨
Delivered = Dict[str, float]                            # delivered_so_far[cid] = 吨
WeightProfile = Dict[Tuple[str, str, str], Tuple[float, float]]  # (w,receiver,k)->(mu,hi)
DelayProfile = Dict[Tuple[str, str], Dict[int, float]]          # (w,receiver)->{delta:prob}
InTransitOrders = List[Dict]                            # 在途报单（dict口径）


def default_global_delay_pmf() -> Dict[int, float]:
    """默认延迟分布：90%隔天到达，其余分散在0/2/3"""
    return {0: 0.0333, 1: 0.90, 2: 0.0333, 3: 0.0334}


def get_delay_dist(
    w: str,
    receiver: str,
    delay_profile: Optional[DelayProfile] = None,
    global_delay_pmf: Optional[Dict[int, float]] = None,
) -> Dict[int, float]:
    """获取某仓库->收货方的延迟分布（Δ->概率），缺失则用全局默认分布"""
    if global_delay_pmf is None:
        global_delay_pmf = default_global_delay_pmf()
    if delay_profile is None:
        return global_delay_pmf
    dist = delay_profile.get((w, receiver), None)
    return dist if dist else global_delay_pmf


def get_mu_hi(
    w: str,
    receiver: str,
    k: str,
    weight_profile: WeightProfile,
    default_mu_hi: Tuple[float, float] = (32.0, 35.0),
) -> Tuple[float, float]:
    """
    获取 lane(仓库,收货方,品类) 的估重画像 (mu, hi)；
    缺失时返回默认值，并做保护（mu<=35, hi>=mu, hi<=35）
    """
    mu_hi = weight_profile.get((w, receiver, k), None)
    if mu_hi is None:
        mu, hi = default_mu_hi
    else:
        mu, hi = mu_hi
    mu = min(max(float(mu), 1.0), 35.0)
    hi = min(max(float(hi), mu), 35.0)
    return mu, hi


def build_cid_receiver_maps(contracts: List[Contract]) -> Tuple[Dict[str, str], Dict[str, str]]:
    """构建映射：receiver_by_cid / cid_by_receiver（假设 receiver 唯一活跃合同）"""
    receiver_by_cid = {c.cid: c.receiver for c in contracts}
    cid_by_receiver = {c.receiver: c.cid for c in contracts}
    return receiver_by_cid, cid_by_receiver


def predict_intransit_arrivals_expected(
    contracts: List[Contract],
    in_transit_orders: InTransitOrders,
    weight_profile: WeightProfile,
    delay_profile: Optional[DelayProfile] = None,
    global_delay_pmf: Optional[Dict[int, float]] = None,
    default_mu_hi: Tuple[float, float] = (32.0, 35.0),
) -> Tuple[Dict[Tuple[str, int], float], Dict[Tuple[str, int], float]]:
    """
    在途报单 -> 未来各日预计到货（期望/偏重上界），按延迟分布分摊到多个到货日。
    返回：
      pred_mu[(cid, day)]：期望到货吨
      pred_hi[(cid, day)]：偏重上界到货吨（用于保守防超发）
    """
    if global_delay_pmf is None:
        global_delay_pmf = default_global_delay_pmf()

    receiver_by_cid, cid_by_receiver = build_cid_receiver_maps(contracts)

    pred_mu: Dict[Tuple[str, int], float] = {}
    pred_hi: Dict[Tuple[str, int], float] = {}

    for o in in_transit_orders:
        w = o["warehouse"]
        ship_day = int(o["ship_day"])
        k = o.get("category", None)
        receiver = o.get("receiver", None)
        cid = o.get("cid", None)

        if receiver is None and cid is not None:
            receiver = receiver_by_cid.get(cid, None)
        if cid is None and receiver is not None:
            cid = cid_by_receiver.get(receiver, None)

        if cid is None or receiver is None or k is None:
            continue

        mu_o, hi_o = get_mu_hi(w, receiver, k, weight_profile, default_mu_hi=default_mu_hi)
        dist = get_delay_dist(w, receiver, delay_profile=delay_profile, global_delay_pmf=global_delay_pmf)

        for delta, p in dist.items():
            d = ship_day + int(delta)
            pred_mu[(cid, d)] = pred_mu.get((cid, d), 0.0) + mu_o * float(p)
            pred_hi[(cid, d)] = pred_hi.get((cid, d), 0.0) + hi_o * float(p)

    return pred_mu, pred_hi


def intransit_total_expected_in_valid_window(
    cid: str,
    pred_mu: Dict[Tuple[str, int], float],
    day_from: int,
    day_to: int,
) -> float:
    """计算合同 cid 在 [day_from, day_to] 的在途期望到货吨数总和"""
    total = 0.0
    for d in range(day_from, day_to + 1):
        total += float(pred_mu.get((cid, d), 0.0))
    return total


def suggest_trucks_from_tons_plan(
    tons_plan: Dict[Tuple[str, str, str, int], float],
    contracts: List[Contract],
    weight_profile: WeightProfile,
    default_mu_hi: Tuple[float, float] = (32.0, 35.0),
) -> Dict[Tuple[str, str, str, int], int]:
    """将吨计划换算为建议车数：trucks = ceil(tons / mu_lane)"""
    receiver_by_cid, _ = build_cid_receiver_maps(contracts)
    truck_suggest: Dict[Tuple[str, str, str, int], int] = {}
    for (w, cid, k, t), tons in tons_plan.items():
        receiver = receiver_by_cid.get(cid, "")
        mu, _hi = get_mu_hi(w, receiver, k, weight_profile, default_mu_hi=default_mu_hi)
        trucks = int(math.ceil(float(tons) / mu))
        truck_suggest[(w, cid, k, t)] = trucks
    return truck_suggest


def calc_purchase_price_per_ton(
    contract_unit_price: float,          # 合同含票单价（元/吨）
    invoice_factor: float = 1.048,       # 票点（默认1.048）
    const: float = 0.0,                  # 仓库常数项（元/吨），于娇娇/王菲仓=10，其它=0
) -> float:
    """
    采购价口径：基础价 * 票点 + 常数

    默认基础价从合同含票价反推：
        base_price = contract_unit_price / invoice_factor

    备注：
    - 按此默认口径，最终 price = contract_unit_price + const
      但保留“*票点+常数”的形式，便于未来基础价不从合同价反推时直接替换。
    """
    if invoice_factor <= 0:
        invoice_factor = 1.0
    base_price = float(contract_unit_price) / float(invoice_factor)
    return base_price * float(invoice_factor) + float(const)
