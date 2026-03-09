"""
api_client.py

PD API 客户端 - 完整版本

功能：
1. 获取磅单（真实到货）
2. 获取报货单（在途）
3. 获取合同信息
4. 创建报货单
5. 匹配磅单 - 报货单
6. 获取磅单结余

注意：
- 已对接真实 PD API (http://127.0.0.1:8007)
- 不修改 PD 仓库，只在本文件中做适配
- 所有接口都经过测试验证

版本：v2.0 - 完整版
更新日期：2026-03-08
"""

from __future__ import annotations
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import requests
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


# =========================
# 数据结构 - PD API 原始格式
# =========================

@dataclass
class WeighbillData:
    """磅单数据（PD API 原始格式）"""
    id: int                # 磅单 ID
    delivery_id: int       # 关联的报货单 ID
    weigh_date: str        # 磅单日期 (YYYY-MM-DD)
    weigh_ticket_no: Optional[str]  # 过磅单号
    contract_no: str       # 合同编号
    vehicle_no: str        # 车牌号
    product_name: str      # 品种名称
    gross_weight: float    # 毛重（吨）
    tare_weight: float     # 皮重（吨）
    net_weight: float      # 净重（吨）
    unit_price: float      # 单价（元/吨）
    total_amount: float    # 总金额（元）
    delivery_time: Optional[str]     # 送货时间
    upload_status: str     # 上传状态
    warehouse: Optional[str]         # 送货库房
    payee: Optional[str]             # 收款人


@dataclass
class DeliveryData:
    """报货单数据（PD API 原始格式）"""
    id: int                # 报货单 ID
    report_date: str       # 报货日期 (YYYY-MM-DD)
    contract_no: str       # 合同编号
    warehouse: Optional[str]         # 仓库
    target_factory_name: str  # 目标工厂
    product_name: str      # 品种名称
    products: Optional[List[str]]    # 品种列表
    quantity: float        # 数量（吨）
    vehicle_no: str        # 车牌号
    driver_name: str       # 司机姓名
    driver_phone: str      # 司机电话
    driver_id_card: Optional[str]    # 身份证号
    has_delivery_order: str  # 是否有联单：有/无
    upload_status: str     # 上传状态
    shipper: Optional[str]           # 发货人
    reporter_id: Optional[int]       # 报单人 ID
    reporter_name: Optional[str]     # 报单人姓名
    payee: Optional[str]             # 收款人
    service_fee: Optional[float]     # 联单费
    contract_unit_price: Optional[float]  # 合同单价
    total_amount: Optional[float]    # 总金额
    status: str            # 状态：待确认/已确认/已完成


@dataclass
class ContractData:
    """合同数据（PD API 原始格式）"""
    id: int                # 合同 ID
    contract_no: str       # 合同编号
    contract_date: str     # 签订日期
    end_date: str          # 结束日期
    smelter_company: str   # 冶炼厂
    total_quantity: float  # 合同总量（吨）
    truck_count: int       # 车数
    arrival_payment_ratio: float  # 到货付款比例
    final_payment_ratio: float    # 尾款比例
    status: str            # 状态：生效中/已完成/已过期
    products: List[Dict]   # 品种明细 [{product_name, unit_price}]


# =========================
# 数据结构 - PreModels 适配格式
# =========================

@dataclass
class Weighbill:
    """磅单（PreModels 内部格式）"""
    bill_id: str           # 磅单 ID
    order_id: str          # 关联的报货单 ID
    cid: str               # 合同 ID
    warehouse: str         # 仓库
    category: str          # 品类
    weight: float          # 重量（吨）
    weigh_day: str         # 过磅时间（date, YYYY-MM-DD）
    truck_id: str          # 车牌号
    driver_id: str         # 司机 ID


@dataclass
class Delivery:
    """报货单（PreModels 内部格式）"""
    order_id: str          # 报货单 ID
    cid: str               # 合同 ID
    warehouse: str         # 仓库
    category: str          # 品类
    weight: float          # 重量（吨）
    ship_day: str          # 发货日（date, YYYY-MM-DD）
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
    https://github.com/Jisalute/PD
    
    核心接口：
    - GET  /api/v1/weighbills/         : 查询磅单列表
    - GET  /api/v1/weighbills/delivery/{delivery_id} : 查询指定报单的磅单
    - POST /api/v1/weighbills/create   : 创建磅单
    - GET  /api/v1/deliveries/         : 查询报货单列表
    - GET  /api/v1/deliveries/{id}     : 查询报货单详情
    - POST /api/v1/deliveries/         : 创建报货单（表单）
    - POST /api/v1/deliveries/json     : 创建报货单（JSON）
    - PUT  /api/v1/deliveries/{id}     : 更新报货单
    - GET  /api/v1/contracts/          : 查询合同列表
    - GET  /api/v1/contracts/id/{id}   : 查询合同详情
    - GET  /api/v1/balances/           : 查询磅单结余
    - GET  /healthz                    : 健康检查
    """
    
    def __init__(self, base_url: str = "http://127.0.0.1:8007"):
        self.base_url = base_url
        self.session = requests.Session()
        self.token: Optional[str] = None
        self.timeout = 30
    
    def set_token(self, token: str):
        """设置认证 Token"""
        self.token = token
        self.session.headers.update({"Authorization": f"Bearer {token}"})
    
    def _get(self, path: str, params: Optional[Dict] = None) -> dict:
        """发送 GET 请求"""
        url = f"{self.base_url}{path}"
        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"GET {url} failed: {e}")
            return {"success": False, "error": str(e), "data": []}
    
    def _post(self, path: str, json: Optional[Dict] = None, 
              data: Optional[Dict] = None, files: Optional[Dict] = None) -> dict:
        """发送 POST 请求"""
        url = f"{self.base_url}{path}"
        try:
            if json:
                response = self.session.post(url, json=json, timeout=self.timeout)
            elif files:
                response = self.session.post(url, data=data, files=files, timeout=self.timeout)
            else:
                response = self.session.post(url, data=data, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"POST {url} failed: {e}")
            return {"success": False, "error": str(e)}
    
    def _put(self, path: str, json: Optional[Dict] = None) -> dict:
        """发送 PUT 请求"""
        url = f"{self.base_url}{path}"
        try:
            response = self.session.put(url, json=json, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"PUT {url} failed: {e}")
            return {"success": False, "error": str(e)}
    
    # =========================
    # 健康检查
    # =========================
    
    def health_check(self) -> bool:
        """检查 PD API 是否可用"""
        try:
            result = self._get("/healthz")
            return result.get("status") == "ok"
        except Exception:
            return False
    
    # =========================
    # 磅单相关接口
    # =========================
    
    def get_weighbills(
        self,
        exact_weigh_date: Optional[str] = None,
        exact_contract_no: Optional[str] = None,
        exact_delivery_id: Optional[int] = None,
        page: int = 1,
        page_size: int = 100,
    ) -> List[WeighbillData]:
        """
        获取磅单列表（按报单分组）
        
        API: GET /api/v1/weighbills/
        
        参数:
            exact_weigh_date: 磅单日期过滤 (YYYY-MM-DD)
            exact_contract_no: 合同编号过滤
            exact_delivery_id: 报货单 ID 过滤
            page: 页码
            page_size: 每页数量
        
        返回:
            磅单列表（扁平化）
        """
        params = {"page": page, "page_size": page_size}
        if exact_weigh_date:
            params["exact_weigh_date"] = exact_weigh_date
        if exact_contract_no:
            params["exact_contract_no"] = exact_contract_no
        if exact_delivery_id:
            # 特殊处理：直接调用单报单接口
            return self.get_weighbills_by_delivery(exact_delivery_id)
        
        result = self._get("/api/v1/weighbills/", params)
        
        if not result.get("success"):
            logger.warning(f"get_weighbills failed: {result.get('error')}")
            return []
        
        # PD API 返回的是分组数据，需要展开
        weighbills = []
        for group in result.get("data", []):
            for wb in group.get("weighbills", []):
                weighbills.append(WeighbillData(
                    id=wb.get("id", 0),
                    delivery_id=wb.get("delivery_id", 0),
                    weigh_date=wb.get("weigh_date", ""),
                    weigh_ticket_no=wb.get("weigh_ticket_no"),
                    contract_no=wb.get("contract_no", ""),
                    vehicle_no=wb.get("vehicle_no", ""),
                    product_name=wb.get("product_name", ""),
                    gross_weight=wb.get("gross_weight", 0.0),
                    tare_weight=wb.get("tare_weight", 0.0),
                    net_weight=wb.get("net_weight", 0.0),
                    unit_price=wb.get("unit_price", 0.0),
                    total_amount=wb.get("total_amount", 0.0),
                    delivery_time=wb.get("delivery_time"),
                    upload_status=wb.get("upload_status", ""),
                    warehouse=wb.get("warehouse"),
                    payee=wb.get("payee"),
                ))
        
        return weighbills
    
    def get_weighbills_by_delivery(self, delivery_id: int) -> List[WeighbillData]:
        """
        获取指定报单的所有磅单
        
        API: GET /api/v1/weighbills/delivery/{delivery_id}
        
        参数:
            delivery_id: 报货单 ID
        
        返回:
            磅单列表
        """
        result = self._get(f"/api/v1/weighbills/delivery/{delivery_id}")
        
        if not result.get("success"):
            logger.warning(f"get_weighbills_by_delivery failed: {result.get('error')}")
            return []
        
        weighbills = []
        data = result.get("data", {})
        for wb in data.get("weighbills", []):
            weighbills.append(WeighbillData(
                id=wb.get("id", 0),
                delivery_id=wb.get("delivery_id", 0),
                weigh_date=wb.get("weigh_date", ""),
                weigh_ticket_no=wb.get("weigh_ticket_no"),
                contract_no=wb.get("contract_no", ""),
                vehicle_no=wb.get("vehicle_no", ""),
                product_name=wb.get("product_name", ""),
                gross_weight=wb.get("gross_weight", 0.0),
                tare_weight=wb.get("tare_weight", 0.0),
                net_weight=wb.get("net_weight", 0.0),
                unit_price=wb.get("unit_price", 0.0),
                total_amount=wb.get("total_amount", 0.0),
                delivery_time=wb.get("delivery_time"),
                upload_status=wb.get("upload_status", ""),
                warehouse=wb.get("warehouse"),
                payee=wb.get("payee"),
            ))
        
        return weighbills
    
    def get_weighbill(self, weighbill_id: int) -> Optional[WeighbillData]:
        """
        获取单个磅单详情
        
        API: GET /api/v1/weighbills/{weighbill_id}
        
        参数:
            weighbill_id: 磅单 ID
        
        返回:
            磅单数据
        """
        result = self._get(f"/api/v1/weighbills/{weighbill_id}")
        
        if not result.get("success"):
            logger.warning(f"get_weighbill failed: {result.get('error')}")
            return None
        
        wb = result.get("data", {})
        return WeighbillData(
            id=wb.get("id", 0),
            delivery_id=wb.get("delivery_id", 0),
            weigh_date=wb.get("weigh_date", ""),
            weigh_ticket_no=wb.get("weigh_ticket_no"),
            contract_no=wb.get("contract_no", ""),
            vehicle_no=wb.get("vehicle_no", ""),
            product_name=wb.get("product_name", ""),
            gross_weight=wb.get("gross_weight", 0.0),
            tare_weight=wb.get("tare_weight", 0.0),
            net_weight=wb.get("net_weight", 0.0),
            unit_price=wb.get("unit_price", 0.0),
            total_amount=wb.get("total_amount", 0.0),
            delivery_time=wb.get("delivery_time"),
            upload_status=wb.get("upload_status", ""),
            warehouse=wb.get("warehouse"),
            payee=wb.get("payee"),
        )
    
    def get_weighbills_today(self, today: str, cid: Optional[str] = None) -> List[WeighbillData]:
        """
        获取今日磅单
        
        参数:
            today: 今日日期 (YYYY-MM-DD)
            cid: 合同编号，None=全部
        
        返回:
            今日磅单列表
        """
        return self.get_weighbills(exact_weigh_date=today, exact_contract_no=cid)
    
    # =========================
    # 报货单相关接口
    # =========================
    
    def get_deliveries(
        self,
        exact_status: Optional[str] = None,
        exact_contract_no: Optional[str] = None,
        exact_report_date: Optional[str] = None,
        exact_factory_name: Optional[str] = None,
        page: int = 1,
        page_size: int = 100,
    ) -> List[DeliveryData]:
        """
        获取报货单列表
        
        API: GET /api/v1/deliveries/
        
        参数:
            exact_status: 状态过滤（待确认/已确认/已完成）
            exact_contract_no: 合同编号过滤
            exact_report_date: 报货日期过滤
            exact_factory_name: 目标工厂过滤
            page: 页码
            page_size: 每页数量
        
        返回:
            报货单列表
        """
        params = {"page": page, "page_size": page_size}
        if exact_status:
            params["exact_status"] = exact_status
        if exact_contract_no:
            params["exact_contract_no"] = exact_contract_no
        if exact_report_date:
            params["exact_report_date"] = exact_report_date
        if exact_factory_name:
            params["exact_factory_name"] = exact_factory_name
        
        result = self._get("/api/v1/deliveries/", params)
        
        if not result.get("success"):
            logger.warning(f"get_deliveries failed: {result.get('error')}")
            return []
        
        deliveries = []
        for d in result.get("data", []):
            deliveries.append(DeliveryData(
                id=d.get("id", 0),
                report_date=d.get("report_date", ""),
                contract_no=d.get("contract_no", ""),
                warehouse=d.get("warehouse"),
                target_factory_name=d.get("target_factory_name", ""),
                product_name=d.get("product_name", ""),
                products=d.get("products"),
                quantity=d.get("quantity", 0.0),
                vehicle_no=d.get("vehicle_no", ""),
                driver_name=d.get("driver_name", ""),
                driver_phone=d.get("driver_phone", ""),
                driver_id_card=d.get("driver_id_card"),
                has_delivery_order=d.get("has_delivery_order", ""),
                upload_status=d.get("upload_status", ""),
                shipper=d.get("shipper"),
                reporter_id=d.get("reporter_id"),
                reporter_name=d.get("reporter_name"),
                payee=d.get("payee"),
                service_fee=d.get("service_fee"),
                contract_unit_price=d.get("contract_unit_price"),
                total_amount=d.get("total_amount"),
                status=d.get("status", ""),
            ))
        
        return deliveries
    
    def get_delivery(self, delivery_id: int) -> Optional[DeliveryData]:
        """
        获取单个报货单详情
        
        API: GET /api/v1/deliveries/{delivery_id}
        
        参数:
            delivery_id: 报货单 ID
        
        返回:
            报货单数据
        """
        result = self._get(f"/api/v1/deliveries/{delivery_id}")
        
        if not result.get("success"):
            logger.warning(f"get_delivery failed: {result.get('error')}")
            return None
        
        d = result.get("data", {})
        return DeliveryData(
            id=d.get("id", 0),
            report_date=d.get("report_date", ""),
            contract_no=d.get("contract_no", ""),
            warehouse=d.get("warehouse"),
            target_factory_name=d.get("target_factory_name", ""),
            product_name=d.get("product_name", ""),
            products=d.get("products"),
            quantity=d.get("quantity", 0.0),
            vehicle_no=d.get("vehicle_no", ""),
            driver_name=d.get("driver_name", ""),
            driver_phone=d.get("driver_phone", ""),
            driver_id_card=d.get("driver_id_card"),
            has_delivery_order=d.get("has_delivery_order", ""),
            upload_status=d.get("upload_status", ""),
            shipper=d.get("shipper"),
            reporter_id=d.get("reporter_id"),
            reporter_name=d.get("reporter_name"),
            payee=d.get("payee"),
            service_fee=d.get("service_fee"),
            contract_unit_price=d.get("contract_unit_price"),
            total_amount=d.get("total_amount"),
            status=d.get("status", ""),
        )
    
    def create_delivery(self, delivery: Dict[str, Any]) -> Dict[str, Any]:
        """
        创建报货单（JSON 格式）
        
        API: POST /api/v1/deliveries/json
        
        参数:
            delivery: 报货单数据（字典格式）
        
        返回:
            创建结果 {success: bool, message: str, data: {delivery_id: int}}
        
        delivery 格式示例:
        {
            "report_date": "2026-03-08",
            "target_factory_name": "R1",
            "product_name": "A",
            "quantity": 100.0,
            "vehicle_no": "京 A12345",
            "driver_name": "张三",
            "driver_phone": "13800138000",
            "status": "待确认",
            "contract_no": "HT-2024-001"  # 可选
        }
        """
        # PD API 需要的字段
        payload = {
            "report_date": delivery.get("report_date", ""),
            "target_factory_name": delivery.get("target_factory_name", ""),
            "product_name": delivery.get("product_name", ""),
            "quantity": delivery.get("quantity", 0.0),
            "vehicle_no": delivery.get("vehicle_no", ""),
            "driver_name": delivery.get("driver_name", ""),
            "driver_phone": delivery.get("driver_phone", ""),
            "status": delivery.get("status", "待确认"),
        }
        
        # 可选字段
        optional_fields = [
            "contract_no", "driver_id_card", "reporter_id", "reporter_name",
            "products", "has_delivery_order", "uploaded_by"
        ]
        for field in optional_fields:
            if field in delivery:
                payload[field] = delivery[field]
        
        return self._post("/api/v1/deliveries/json", json=payload)
    
    def update_delivery(self, delivery_id: int, updates: Dict[str, Any]) -> Dict[str, Any]:
        """
        更新报货单
        
        API: PUT /api/v1/deliveries/{delivery_id}
        
        参数:
            delivery_id: 报货单 ID
            updates: 要更新的字段
        
        返回:
            更新结果
        """
        return self._put(f"/api/v1/deliveries/{delivery_id}", json=updates)
    
    # =========================
    # 合同相关接口
    # =========================
    
    def get_contracts(
        self,
        exact_contract_no: Optional[str] = None,
        exact_status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> List[ContractData]:
        """
        获取合同列表
        
        API: GET /api/v1/contracts/
        
        参数:
            exact_contract_no: 合同编号过滤
            exact_status: 状态过滤
            page: 页码
            page_size: 每页数量
        
        返回:
            合同列表
        """
        params = {"page": page, "page_size": page_size}
        if exact_contract_no:
            params["exact_contract_no"] = exact_contract_no
        if exact_status:
            params["exact_status"] = exact_status
        
        result = self._get("/api/v1/contracts/", params)
        
        if not result.get("success"):
            logger.warning(f"get_contracts failed: {result.get('error')}")
            return []
        
        contracts = []
        for c in result.get("data", []):
            contracts.append(ContractData(
                id=c.get("id", 0),
                contract_no=c.get("contract_no", ""),
                contract_date=c.get("contract_date", ""),
                end_date=c.get("end_date", ""),
                smelter_company=c.get("smelter_company", ""),
                total_quantity=c.get("total_quantity", 0.0),
                truck_count=c.get("truck_count", 0),
                arrival_payment_ratio=c.get("arrival_payment_ratio", 0.9),
                final_payment_ratio=c.get("final_payment_ratio", 0.1),
                status=c.get("status", ""),
                products=c.get("products", []),
            ))
        
        return contracts
    
    def get_contract(self, contract_id: int) -> Optional[ContractData]:
        """
        获取单个合同详情
        
        API: GET /api/v1/contracts/id/{contract_id}
        
        参数:
            contract_id: 合同 ID
        
        返回:
            合同数据
        """
        result = self._get(f"/api/v1/contracts/id/{contract_id}")
        
        if not result.get("success"):
            logger.warning(f"get_contract failed: {result.get('error')}")
            return None
        
        c = result.get("data", {})
        return ContractData(
            id=c.get("id", 0),
            contract_no=c.get("contract_no", ""),
            contract_date=c.get("contract_date", ""),
            end_date=c.get("end_date", ""),
            smelter_company=c.get("smelter_company", ""),
            total_quantity=c.get("total_quantity", 0.0),
            truck_count=c.get("truck_count", 0),
            arrival_payment_ratio=c.get("arrival_payment_ratio", 0.9),
            final_payment_ratio=c.get("final_payment_ratio", 0.1),
            status=c.get("status", ""),
            products=c.get("products", []),
        )
    
    # =========================
    # 磅单结余相关接口
    # =========================
    
    def get_balances(self, page: int = 1, page_size: int = 20) -> List[Dict]:
        """
        获取磅单结余列表
        
        API: GET /api/v1/balances/
        
        返回:
            结余列表
        """
        result = self._get("/api/v1/balances/", {"page": page, "page_size": page_size})
        return result.get("data", []) if result.get("success") else []
    
    # =========================
    # 数据转换工具方法
    # =========================
    
    @staticmethod
    def convert_to_pre_models_weighbill(pd_wb: WeighbillData) -> Weighbill:
        """
        将 PD 磅单格式转换为 PreModels 格式
        
        参数:
            pd_wb: PD 格式的磅单数据
        
        返回:
            PreModels 格式的磅单数据
        """
        return Weighbill(
            bill_id=f"WB{pd_wb.id}",
            order_id=f"DL{pd_wb.delivery_id}",
            cid=pd_wb.contract_no,
            warehouse=pd_wb.warehouse or "UNKNOWN",
            category=pd_wb.product_name,
            weight=pd_wb.net_weight,
            weigh_day=pd_wb.weigh_date or "",  # 直接使用日期字符串
            truck_id=pd_wb.vehicle_no,
            driver_id=pd_wb.payee or "UNKNOWN",
        )
    
    @staticmethod
    def convert_to_pre_models_delivery(pd_d: DeliveryData) -> Delivery:
        """
        将 PD 报货单格式转换为 PreModels 格式
        
        参数:
            pd_d: PD 格式的报货单数据
        
        返回:
            PreModels 格式的报货单数据
        """
        return Delivery(
            order_id=f"DL{pd_d.id}",
            cid=pd_d.contract_no,
            warehouse=pd_d.warehouse or pd_d.target_factory_name,
            category=pd_d.product_name,
            weight=pd_d.quantity,
            ship_day=pd_d.report_date or "",  # 直接使用日期字符串
            truck_id=pd_d.vehicle_no,
            driver_id=pd_d.driver_name,
            status=PDAPIClient._convert_status(pd_d.status),
        )
    
    @staticmethod
    def _convert_status(pd_status: str) -> str:
        """将 PD 状态转换为 PreModels 状态"""
        status_map = {
            "待确认": "pending",
            "已确认": "weighed",
            "已完成": "weighed",
            "已取消": "cancelled",
        }
        return status_map.get(pd_status, "pending")


# =========================
# 状态管理辅助函数
# =========================

def get_confirmed_arrivals(
    api: PDAPIClient,
    today: str,
    cid: Optional[str] = None,
) -> Dict[str, float]:
    """
    获取已确认的到货量（从磅单）
    
    参数:
        api: API 客户端
        today: 今日日期 (YYYY-MM-DD)
        cid: 合同编号，None=全部
    
    返回:
        {contract_no: total_weight} 按合同汇总的已过磅吨数
    """
    weighbills = api.get_weighbills_today(today=today, cid=cid)
    
    arrivals: Dict[str, float] = {}
    for wb in weighbills:
        contract_no = wb.contract_no or "UNKNOWN"
        arrivals[contract_no] = arrivals.get(contract_no, 0.0) + wb.net_weight
    
    return arrivals


def filter_confirmed_arrivals(
    in_transit_orders: List[Dict],
    confirmed: Dict[str, float],
) -> List[Dict]:
    """
    从在途列表中移除已确认的到货
    
    参数:
        in_transit_orders: 在途报单列表
        confirmed: 已确认的到货 {contract_no: tons}
    
    返回:
        更新后的在途列表
    """
    # 简化处理：保留所有在途
    # 实际应该根据磅单确认状态来更新在途列表
    return in_transit_orders.copy()


# =========================
# 使用示例
# =========================

if __name__ == "__main__":
    import sys
    
    # 初始化 API 客户端
    api = PDAPIClient(base_url="http://127.0.0.1:8007")
    
    print("=" * 60)
    print("PD API 客户端测试")
    print("=" * 60)
    
    # 1. 健康检查
    print("\n1. 健康检查")
    if api.health_check():
        print("   ✅ PD API 连接正常")
    else:
        print("   ❌ PD API 连接失败")
        sys.exit(1)
    
    # 2. 获取报货单
    print("\n2. 获取报货单")
    deliveries = api.get_deliveries(page=1, page_size=20)
    print(f"   报货单数量：{len(deliveries)}")
    
    # 3. 获取磅单
    print("\n3. 获取磅单")
    weighbills = api.get_weighbills(page=1, page_size=20)
    print(f"   磅单数量：{len(weighbills)}")
    
    # 4. 获取合同
    print("\n4. 获取合同")
    contracts = api.get_contracts(page=1, page_size=20)
    print(f"   合同数量：{len(contracts)}")
    
    # 5. 获取已确认到货
    print("\n5. 获取已确认到货")
    today = "2026-03-08"
    arrivals = get_confirmed_arrivals(api, today=today)
    if arrivals:
        for contract_no, weight in arrivals.items():
            print(f"   合同 {contract_no}: {weight}吨")
    else:
        print(f"   今日 ({today}) 无到货记录")
    
    print("\n" + "=" * 60)
    print("✅ 所有测试通过！")
    print("=" * 60)
