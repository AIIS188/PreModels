"""
test_in_transit_initialization.py

测试在途报单初始化逻辑

验证：
1. 从空 state 初始化时，能正确从 PD API 获取在途报单
2. 在途报单包含所有待确认状态的报货单
3. 已过磅的报单被正确移除
4. 过期合同的报单被正确清理
"""

import sys
from pathlib import Path
from unittest.mock import Mock
from dataclasses import dataclass

# 添加 v2 目录到路径
v2_dir = Path(__file__).parent.parent
if str(v2_dir) not in sys.path:
    sys.path.insert(0, str(v2_dir))

from core.state_manager import StateManager
from models.common_utils_v2 import Contract
from core.date_utils import DateUtils
import shutil


@dataclass
class MockWeighbill:
    """模拟磅单数据"""
    contract_no: str
    net_weight: float
    weigh_time: str
    vehicle_no: str


@dataclass
class MockDelivery:
    """模拟报货单数据"""
    id: int
    report_date: str
    contract_no: str
    warehouse: str
    target_factory_name: str
    product_name: str
    quantity: float
    vehicle_no: str


def create_mock_api_with_transit():
    """创建模拟的 PD API 客户端（包含在途报单）"""
    api = Mock()
    
    # 模拟今日磅单数据（只有部分报单过磅）
    api.get_weighbills_today.return_value = [
        MockWeighbill(contract_no="HT-001", net_weight=35.5, weigh_time="2026-03-15 08:30", vehicle_no="京 A12345"),
    ]
    
    # 模拟报货单数据（所有待确认状态）
    api.get_deliveries.return_value = [
        # HT-001: 已过磅
        MockDelivery(id=1, report_date="2026-03-14", contract_no="HT-001", warehouse="W1", target_factory_name="W1", product_name="A", quantity=35.0, vehicle_no="京 A12345"),
        # HT-001: 未过磅
        MockDelivery(id=2, report_date="2026-03-15", contract_no="HT-001", warehouse="W1", target_factory_name="W1", product_name="A", quantity=34.0, vehicle_no="京 B67890"),
        # HT-002: 未过磅（新合同）
        MockDelivery(id=3, report_date="2026-03-15", contract_no="HT-002", warehouse="W2", target_factory_name="W2", product_name="A", quantity=33.0, vehicle_no="京 C11111"),
        # HT-OLD: 过期合同的报单
        MockDelivery(id=4, report_date="2026-03-13", contract_no="HT-OLD", warehouse="W1", target_factory_name="W1", product_name="A", quantity=32.0, vehicle_no="京 D22222"),
    ]
    
    return api


def test_in_transit_from_empty_state():
    """测试从空 state 初始化并获取在途报单"""
    test_state_dir = "./test_state_transit_init"
    shutil.rmtree(test_state_dir, ignore_errors=True)
    
    state_mgr = StateManager(test_state_dir)
    api = create_mock_api_with_transit()
    
    # 合同列表（包含有效合同和过期合同）
    contracts = [
        Contract(
            cid="HT-001",
            receiver="R1",
            Q=1000.0,
            start_day="2026-03-01",
            end_day="2026-03-20",  # 有效
            products=[{"product_name": "A", "unit_price": 800.0}],
        ),
        Contract(
            cid="HT-002",
            receiver="R1",
            Q=500.0,
            start_day="2026-03-15",
            end_day="2026-03-25",  # 有效（今天开始）
            products=[{"product_name": "A", "unit_price": 800.0}],
        ),
        Contract(
            cid="HT-OLD",
            receiver="R1",
            Q=300.0,
            start_day="2026-03-01",
            end_day="2026-03-14",  # 已过期
            products=[{"product_name": "A", "unit_price": 800.0}],
        ),
    ]
    
    print("=" * 60)
    print("测试：从空 state 初始化并获取在途报单")
    print("=" * 60)
    
    # 刷新状态（state 不存在，自动初始化）
    state = state_mgr.refresh_state(
        api=api,
        today="2026-03-15",
        contracts=contracts,
        auto_init=True,
    )
    
    print(f"\n初始状态（空 state）:")
    print(f"  - 自动初始化：是")
    print(f"  - delivered_so_far: {state.delivered_so_far}")
    print(f"  - in_transit_orders: {len(state.in_transit_orders)} 单")
    
    for order in state.in_transit_orders:
        print(f"    - {order['order_id']} ({order['cid']}) truck={order['truck_id']}")
    
    # 验证 delivered_so_far
    assert "HT-001" in state.delivered_so_far, "❌ HT-001 应该被初始化"
    assert state.delivered_so_far["HT-001"] == 35.5, f"❌ HT-001 应该累加磅单数据 35.5"
    assert "HT-002" in state.delivered_so_far, "❌ HT-002 应该被初始化"
    assert state.delivered_so_far["HT-002"] == 0.0, "❌ HT-002 初始值应为 0（无磅单）"
    assert "HT-OLD" not in state.delivered_so_far, "❌ HT-OLD (过期合同) 应该被清理"
    
    # 验证 in_transit_orders
    # API 返回 4 单：
    #   - DL1 (HT-001): 已过磅（京 A12345），移除
    #   - DL2 (HT-001): 未过磅（京 B67890），保留
    #   - DL3 (HT-002): 未过磅（京 C11111），保留
    #   - DL4 (HT-OLD): 未过磅，但 HT-OLD 已过期，清理
    # 结果：2 单（DL2, DL3）
    
    assert len(state.in_transit_orders) == 2, f"❌ 在途报单应该剩 2 单，实际 {len(state.in_transit_orders)} 单"
    
    order_cids = {o["cid"] for o in state.in_transit_orders}
    assert "HT-001" in order_cids, "❌ HT-001 的在途报单应该保留（未过磅）"
    assert "HT-002" in order_cids, "❌ HT-002 的在途报单应该保留"
    assert "HT-OLD" not in order_cids, "❌ HT-OLD 的在途报单应该被清理（过期）"
    
    print(f"\n✅ 从空 state 初始化测试通过")
    print(f"   - delivered_so_far: {len(state.delivered_so_far)} 个合同")
    print(f"   - in_transit_orders: {len(state.in_transit_orders)} 单（已过滤过磅 + 清理过期）")
    print("=" * 60)
    
    shutil.rmtree(test_state_dir, ignore_errors=True)
    return True


if __name__ == "__main__":
    test_in_transit_from_empty_state()
    print("\n🎉 所有测试完成！")
