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
from core.date_utils import DateUtils    #引入日期工具类

# =========================
# 结构体：合同
# =========================

@dataclass(frozen=True)
class Contract:
    cid: str                      # 合同 ID
    receiver: str                 # 收货方（同一收货方仅 1 个活跃合同）
    Q: float                      # 合同总量（吨）
    start_day: str                # 到货有效期开始
    end_day: str                  # 到货有效期结束
    products: List[Dict]          # 品类明细（价格锁定）[{product_name, unit_price}]
                                  # 例：[{"product_name": "动力煤", "unit_price": 800.0}]
                                  # 一个合同可包含多个品类，合同期内价格不可调整
    
    @property
    def allowed_categories(self) -> Set[str]:
        """向后兼容：从 products 提取品类名称集合"""
        return {p["product_name"] for p in self.products}
    
    def get_unit_price(self, product_name: str) -> Optional[float]:
        """获取指定品类的合同单价（元/吨）"""
        for p in self.products:
            if p.get("product_name") == product_name:
                return float(p.get("unit_price", 0.0))
        return None
    
    def get_base_price(self, product_name: str, invoice_factor: float = 1.048) -> Optional[float]:
        """获取指定品类的基础价（不含票）"""
        unit_price = self.get_unit_price(product_name)
        if unit_price is None:
            return None
        return unit_price / invoice_factor


# =========================
# 类型别名
# =========================

CapToday = Dict[Tuple[str, str], float]                 # cap_today[(w,k)] = 吨
CapForecast = Dict[Tuple[str, str, str], float]         # cap_forecast[(w,k,date)] = 吨
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
) -> Tuple[Dict[Tuple[str, str], float], Dict[Tuple[str, str], float]]:
    """
    在途报单 -> 未来各日预计到货（期望/偏重上界），按延迟分布分摊到多个到货日。
    返回：
      pred_mu[(cid, date)]：期望到货吨
      pred_hi[(cid, date)]：偏重上界到货吨（用于保守防超发）
    """
    if global_delay_pmf is None:
        global_delay_pmf = default_global_delay_pmf()

    receiver_by_cid, cid_by_receiver = build_cid_receiver_maps(contracts)

    pred_mu: Dict[Tuple[str, str], float] = {}
    pred_hi: Dict[Tuple[str, str], float] = {}

    for o in in_transit_orders:
        w = o["warehouse"]
        ship_day = str(o["ship_day"])
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
            d = DateUtils.add_days(ship_day, delta)
            pred_mu[(cid, d)] = pred_mu.get((cid, d), 0.0) + mu_o * float(p)
            pred_hi[(cid, d)] = pred_hi.get((cid, d), 0.0) + hi_o * float(p)

    return pred_mu, pred_hi


def intransit_total_expected_in_valid_window(
    cid: str,
    pred_mu: Dict[Tuple[str, str], float],
    day_from: str,
    day_to: str,
) -> float:
    """计算合同 cid 在 [day_from, day_to] 的在途期望到货吨数总和"""
    total = 0.0
    d = day_from
    while DateUtils.diff_days(d, day_to) >= 0:
        total += float(pred_mu.get((cid, d), 0.0))
        d = DateUtils.add_days(d, 1)
    return total


def suggest_trucks_from_tons_plan(
    tons_plan: Dict[Tuple[str, str, str, str], float],
    contracts: List[Contract],
    weight_profile: WeightProfile,
    default_mu_hi: Tuple[float, float] = (32.0, 35.0),
    allow_mixing: bool = True,  # 新增：是否允许混装
) -> Dict[Tuple[str, str, str], int]:
    """
    将吨计划换算为建议车数
    
    参数:
        tons_plan: {(w, cid, k, date): tons} 吨计划
        allow_mixing: 是否允许混装（默认 True）
            - True: 同一 (w, cid, t) 的不同品类可以拼车
            - False: 每个品类单独计算车数（旧逻辑，向后兼容）
    
    返回:
        {(w, cid, date): trucks} 车数建议
    
    混装模式下的额外输出:
        可通过 get_mixing_details 获取每车的品类分配明细
    """
    receiver_by_cid, _ = build_cid_receiver_maps(contracts)
    
    if not allow_mixing:
        # 旧逻辑：按品类单独计算车数（向后兼容）
        truck_suggest: Dict[Tuple[str, str, str], int] = {}
        for (w, cid, k, t), tons in tons_plan.items():
            receiver = receiver_by_cid.get(cid, "")
            mu, _hi = get_mu_hi(w, receiver, k, weight_profile, default_mu_hi=default_mu_hi)
            trucks = int(math.ceil(float(tons) / mu))
            key = (w, cid, t)
            truck_suggest[key] = truck_suggest.get(key, 0) + trucks
        return truck_suggest
    
    # 新逻辑：支持混装
    # 1. 按 (w, cid, date) 聚合吨数
    tons_by_lane: Dict[Tuple[str, str, str], List[Tuple[str, float]]] = {}
    for (w, cid, k, t), tons in tons_plan.items():
        key = (w, cid, t)
        if key not in tons_by_lane:
            tons_by_lane[key] = []
        tons_by_lane[key].append((k, tons))
    
    # 2. 换算车数（按 lane 估重，混装时使用加权平均 mu）
    truck_suggest: Dict[Tuple[str, str, str], int] = {}
    for (w, cid, t), category_tons in tons_by_lane.items():
        receiver = receiver_by_cid.get(cid, "")

        total_tons = sum(tons for _, tons in category_tons)
        mu, _= get_mu_hi(w, receiver, category_tons[0][0], weight_profile, default_mu_hi=default_mu_hi)  # 取第一个品类的 mu 作为基准
        trucks = int(math.ceil(total_tons / mu)) if mu > 0 else 0 
        
        truck_suggest[(w, cid, t)] = trucks
    
    return truck_suggest


def get_mixing_details(
    tons_plan: Dict[Tuple[str, str, str, str], float],
    contracts: List[Contract],
    weight_profile: WeightProfile,
    default_mu_hi: Tuple[float, float] = (32.0, 35.0),
) -> Dict[Tuple[str, str, int], Dict[str, float]]:
    """
    获取混装明细：各仓库的品类分配建议
    
    返回:
        {(w, cid, t): {category: tons}} 各仓库的品类吨数分配
    
    注：这是简化版本，实际装车时可能需要更复杂的配载优化
    """
    receiver_by_cid, _ = build_cid_receiver_maps(contracts)
    
    # 按 (w, cid, t) 聚合品类吨数
    mixing: Dict[Tuple[str, str, str], Dict[str, float]] = {}
    for (w, cid, k, t), tons in tons_plan.items():
        key = (w, cid, t)
        if key not in mixing:
            mixing[key] = {}
        mixing[key][k] = mixing[key].get(k, 0.0) + tons
    
    return mixing


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
