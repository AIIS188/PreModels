"""
api_client.py

PD API 客户端（预留接口）

功能：
1. 获取磅单（真实到货）
2. 获取报货单（在途）
3. 匹配报单 - 磅单
4. 更新合同状态

注意：
- 当前为预留接口，返回模拟数据
- 对接真实 PD API 时替换实现
"""

from __future__ import annotations
from typing import Dict, List, Optional
from dataclasses import dataclass
import requests


# =========================
# 数据结构
# =========================

@dataclass
class Weighbill:
    """磅单（过磅记录）"""
    bill_id: str           # 磅单 ID
    order_id: str          # 关联的报货单 ID
    cid: str               # 合同 ID
    warehouse: str         # 仓库
    category: str          # 品类
    weight: float          # 重量（吨）
    weigh_time: int        # 过磅时间（day）
    truck_id: str          # 车牌号
    driver_id: str         # 司机 ID


@dataclass
class Delivery:
    """报货单（发货单）"""
    order_id: str          # 报货单 ID
    cid: str               # 合同 ID
    warehouse: str         # 仓库
    category: str          # 品类
    weight: float          # 重量（吨）
    ship_day: int          # 发货日
    truck_id: str          # 车牌号
    driver_id: str         # 司机 ID
    status: str            # 状态：pending/weighed/cancelled


# =========================
# API 客户端
# =========================

class PDAPIClient:
    """
    PD API 客户端
    
    接口文档：
    - GET /api/v1/weighbills: 查询磅单列表
    - GET /api/v1/deliveries: 查询报货单列表
    - POST /api/v1/deliveries: 创建报货单
    """
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session = requests.Session()
    
    # =========================
    # 磅单相关
    # =========================
    
    def get_weighbills(
        self,
        date: Optional[int] = None,
        cid: Optional[str] = None,
        warehouse: Optional[str] = None,
    ) -> List[Weighbill]:
        """
        获取磅单列表
        
        参数:
            date: 过滤日期（day），None=全部
            cid: 合同 ID，None=全部
            warehouse: 仓库，None=全部
        
        返回:
            磅单列表
        
        API:
            GET /api/v1/weighbills?date={date}&cid={cid}&warehouse={warehouse}
        """
        # TODO: 实现真实 API 调用
        # response = self.session.get(f"{self.base_url}/api/v1/weighbills", params={...})
        # response.raise_for_status()
        # return [Weighbill(**item) for item in response.json()]
        
        # 模拟数据（临时）
        return []
    
    def get_weighbills_today(self, cid: Optional[str] = None) -> List[Weighbill]:
        """
        获取今日磅单
        
        参数:
            cid: 合同 ID，None=全部
        
        返回:
            今日磅单列表
        """
        # TODO: 实现真实 API 调用
        return []
    
    # =========================
    # 报货单相关
    # =========================
    
    def get_deliveries(
        self,
        status: Optional[str] = None,
        cid: Optional[str] = None,
    ) -> List[Delivery]:
        """
        获取报货单列表
        
        参数:
            status: 状态过滤（pending/weighed/cancelled），None=全部
            cid: 合同 ID，None=全部
        
        返回:
            报货单列表
        
        API:
            GET /api/v1/deliveries?status={status}&cid={cid}
        """
        # TODO: 实现真实 API 调用
        return []
    
    def create_delivery(self, delivery: Delivery) -> str:
        """
        创建报货单
        
        参数:
            delivery: 报货单数据
        
        返回:
            order_id
        
        API:
            POST /api/v1/deliveries
        """
        # TODO: 实现真实 API 调用
        # response = self.session.post(f"{self.base_url}/api/v1/deliveries", json=delivery.__dict__)
        # response.raise_for_status()
        # return response.json()["order_id"]
        return ""
    
    # =========================
    # 匹配相关
    # =========================
    
    def match_delivery_weighbill(self, order_id: str, bill_id: str) -> bool:
        """
        匹配报货单和磅单
        
        参数:
            order_id: 报货单 ID
            bill_id: 磅单 ID
        
        返回:
            是否匹配成功
        
        API:
            POST /api/v1/weighbills/{bill_id}/match
        """
        # TODO: 实现真实 API 调用
        return True


# =========================
# 状态管理辅助函数
# =========================

def get_confirmed_arrivals(
    api: PDAPIClient,
    today: int,
) -> Dict[str, float]:
    """
    获取已确认的到货量（从磅单）
    
    参数:
        api: API 客户端
        today: 今日（day）
    
    返回:
        {cid: weighed_tons} 按合同汇总的已过磅吨数
    """
    weighbills = api.get_weighbills_today()
    
    arrivals: Dict[str, float] = {}
    for wb in weighbills:
        arrivals[wb.cid] = arrivals.get(wb.cid, 0.0) + wb.weight
    
    return arrivals


def filter_confirmed_arrivals(
    in_transit_orders: List[Dict],
    confirmed: Dict[str, float],
) -> List[Dict]:
    """
    从在途列表中移除已确认的到货
    
    参数:
        in_transit_orders: 在途报单列表
        confirmed: 已确认的到货 {cid: tons}
    
    返回:
        更新后的在途列表
    """
    # 简单实现：按 order_id 匹配（更准确）
    # 假设 confirmed 中的 order_id 在 in_transit_orders 中存在
    remaining = []
    for order in in_transit_orders:
        order_id = order.get("order_id", "")
        
        # 如果此订单已确认，跳过
        # 简单判断：如果 confirmed 中有该 cid 的量，假设按顺序确认
        cid = order.get("cid", "")
        
        # 实际应该按 order_id 精确匹配
        # 这里简化处理：保留所有在途（因为没有真实磅单数据）
        remaining.append(order)
    
    return remaining


# =========================
# 使用示例
# =========================

if __name__ == "__main__":
    # 示例：获取今日磅单并更新状态
    api = PDAPIClient()
    
    # 获取今日已过磅的到货
    today_arrivals = get_confirmed_arrivals(api, today=10)
    print(f"今日到货：{today_arrivals}")
    
    # 更新在途列表
    in_transit = [...]  # 原有在途
    in_transit = filter_confirmed_arrivals(in_transit, today_arrivals)
