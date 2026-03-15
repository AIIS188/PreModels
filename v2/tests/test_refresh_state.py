"""
test_refresh_state.py

测试 StateManager.refresh_state() 方法

验证：
1. 自动初始化（state 不存在时）
2. 从 PD API 获取磅单并累加 delivered_so_far
3. 从 PD API 获取车牌号并更新 in_transit_orders
4. 清理过期合同数据
5. 保存更新后的 state
"""

import sys
from pathlib import Path
from unittest.mock import Mock, MagicMock
from dataclasses import dataclass

# 添加 v2 目录到路径（支持直接运行和 PYTHONPATH 运行）
v2_dir = Path(__file__).parent.parent
if str(v2_dir) not in sys.path:
    sys.path.insert(0, str(v2_dir))

from core.state_manager import StateManager, ModelState
from models.common_utils_v2 import Contract
from core.date_utils import DateUtils
import shutil
import json
import os


@dataclass
class MockWeighbill:
    """模拟磅单数据"""
    contract_no: str
    net_weight: float
    weigh_time: str
    vehicle_no: str  # 车牌号
    truck_id: str = None  # 兼容字段


@dataclass
class MockDelivery:
    """模拟报货单数据（匹配 PD API 的 DeliveryData）"""
    id: int  # 报货单 ID
    report_date: str  # 报货日期
    contract_no: str  # 合同编号
    warehouse: str  # 仓库
    target_factory_name: str  # 目标工厂
    product_name: str  # 品种名称
    quantity: float  # 数量（吨）
    vehicle_no: str  # 车牌号
    # 以下字段可选
    category: str = ""
    ship_day: str = ""
    truck_id: str = ""
    weight: float = 0.0


def create_mock_api():
    """创建模拟的 PD API 客户端"""
    api = Mock()
    
    # 模拟今日磅单数据（注意：get_confirmed_arrivals 使用 get_weighbills_today 和 net_weight）
    # 注意：只包含京 A12345 和 京 B67890，不包含 京 C11111（DL003 未过磅）
    api.get_weighbills_today.return_value = [
        MockWeighbill(contract_no="HT-002", net_weight=35.5, weigh_time="2026-03-15 08:30", vehicle_no="京 A12345"),
        MockWeighbill(contract_no="HT-003", net_weight=34.2, weigh_time="2026-03-15 09:15", vehicle_no="京 B67890"),
    ]
    
    # 模拟报货单数据（用于获取在途 - 所有待确认状态）
    # 注意：get_in_transit_orders 调用 get_deliveries(exact_status="待确认")
    # 这里返回所有待确认的报货单（包括历史的）
    api.get_deliveries.return_value = [
        MockDelivery(id=1, report_date="2026-03-14", contract_no="HT-002", warehouse="W1", target_factory_name="W1", product_name="A", quantity=35.0, vehicle_no="京 A12345"),
        MockDelivery(id=2, report_date="2026-03-14", contract_no="HT-003", warehouse="W2", target_factory_name="W2", product_name="A", quantity=34.0, vehicle_no="京 B67890"),
        MockDelivery(id=3, report_date="2026-03-13", contract_no="HT-001", warehouse="W1", target_factory_name="W1", product_name="A", quantity=33.0, vehicle_no="京 C11111"),  # 过期合同
    ]
    
    return api


def test_refresh_state_auto_init():
    """测试自动初始化功能"""
    test_state_dir = "./test_state_refresh_init"
    shutil.rmtree(test_state_dir, ignore_errors=True)
    
    state_mgr = StateManager(test_state_dir)
    api = create_mock_api()
    
    contracts = [
        Contract(
            cid="HT-001",
            receiver="R1",
            Q=1000.0,
            start_day="2026-03-01",
            end_day="2026-03-14",  # 已过期
            products=[{"product_name": "A", "unit_price": 800.0}],
        ),
        Contract(
            cid="HT-002",
            receiver="R1",
            Q=500.0,
            start_day="2026-03-10",
            end_day="2026-03-15",  # 今天结束
            products=[{"product_name": "A", "unit_price": 800.0}],
        ),
    ]
    
    print("=" * 60)
    print("测试：refresh_state 自动初始化")
    print("=" * 60)
    
    # state 不存在，应该自动初始化
    state = state_mgr.refresh_state(
        api=api,
        today="2026-03-15",
        contracts=contracts,
        auto_init=True,
    )
    
    # 验证 state 已创建
    assert state is not None, "❌ state 应该被创建"
    assert os.path.exists(os.path.join(test_state_dir, "state.json")), "❌ state.json 应该被创建"
    
    # 验证合同已初始化（HT-001 会被初始化但随后被清理）
    assert "HT-002" in state.delivered_so_far, "❌ HT-002 应该被初始化"
    assert state.delivered_so_far["HT-002"] == 35.5, f"❌ HT-002 应该累加磅单数据 35.5，实际 {state.delivered_so_far['HT-002']}"
    
    # 验证过期合同被清理（HT-001 end_day=2026-03-14 < today=2026-03-15）
    assert "HT-001" not in state.delivered_so_far, "❌ HT-001 (过期合同) 应该被清理"
    
    print(f"✅ 自动初始化测试通过")
    print(f"   - delivered_so_far: {state.delivered_so_far}")
    print(f"   - in_transit_orders: {len(state.in_transit_orders)} 单")
    print("=" * 60)
    
    shutil.rmtree(test_state_dir, ignore_errors=True)
    return True


def test_refresh_state_update_existing():
    """测试更新现有 state"""
    test_state_dir = "./test_state_refresh_update"
    shutil.rmtree(test_state_dir, ignore_errors=True)
    
    state_mgr = StateManager(test_state_dir)
    
    # 先初始化一个 state
    initial_state = state_mgr.initialize_state(
        delivered_so_far={"HT-002": 100.0, "HT-003": 200.0},
        in_transit_orders=[
            {"order_id": "DL001", "cid": "HT-002", "warehouse": "W1", "category": "A", "ship_day": "2026-03-14", "truck_id": "京 A12345"},
            {"order_id": "DL002", "cid": "HT-003", "warehouse": "W2", "category": "A", "ship_day": "2026-03-14", "truck_id": "京 B67890"},
        ],
        today="2026-03-14",
    )
    
    api = create_mock_api()
    
    contracts = [
        Contract(
            cid="HT-002",
            receiver="R1",
            Q=500.0,
            start_day="2026-03-10",
            end_day="2026-03-20",
            products=[{"product_name": "A", "unit_price": 800.0}],
        ),
        Contract(
            cid="HT-003",
            receiver="R1",
            Q=800.0,
            start_day="2026-03-12",
            end_day="2026-03-25",
            products=[{"product_name": "A", "unit_price": 800.0}],
        ),
    ]
    
    print("\n" + "=" * 60)
    print("测试：refresh_state 更新现有 state")
    print("=" * 60)
    
    print(f"初始状态:")
    print(f"  - delivered_so_far: {initial_state.delivered_so_far}")
    print(f"  - in_transit_orders: {len(initial_state.in_transit_orders)} 单")
    
    # 刷新状态
    state = state_mgr.refresh_state(
        api=api,
        today="2026-03-15",
        contracts=contracts,
        auto_init=False,
    )
    
    print(f"\n刷新后状态:")
    print(f"  - delivered_so_far: {state.delivered_so_far}")
    print(f"  - in_transit_orders: {len(state.in_transit_orders)} 单")
    
    # 验证累加逻辑
    assert state.delivered_so_far["HT-002"] == 100.0 + 35.5, f"❌ HT-002 应该累加 100.0 + 35.5 = 135.5，实际 {state.delivered_so_far['HT-002']}"
    assert state.delivered_so_far["HT-003"] == 200.0 + 34.2, f"❌ HT-003 应该累加 200.0 + 34.2 = 234.2，实际 {state.delivered_so_far['HT-003']}"
    
    # 验证在途报单更新（已过磅的应该被移除 + 过期合同被清理）
    # API 返回 3 单（DL1, DL2, DL3）：
    #   - DL1 (HT-002): 已过磅（京 A12345），移除
    #   - DL2 (HT-003): 已过磅（京 B67890），移除
    #   - DL3 (HT-001): 未过磅（京 C11111），但 HT-001 已过期（end_day=2026-03-14 < today），清理
    # 结果：0 单
    assert len(state.in_transit_orders) == 0, f"❌ 在途报单应该全部被移除/清理，实际剩余 {len(state.in_transit_orders)} 单"
    
    print(f"✅ 更新现有 state 测试通过")
    print("=" * 60)
    
    shutil.rmtree(test_state_dir, ignore_errors=True)
    return True


def test_refresh_state_no_api():
    """测试无 API 时的降级处理"""
    test_state_dir = "./test_state_refresh_noapi"
    shutil.rmtree(test_state_dir, ignore_errors=True)
    
    state_mgr = StateManager(test_state_dir)
    
    # 创建会抛出异常的 mock API
    api = Mock()
    api.get_weighbills.side_effect = Exception("API 不可用")
    api.get_deliveries.side_effect = Exception("API 不可用")
    
    contracts = [
        Contract(
            cid="HT-002",
            receiver="R1",
            Q=500.0,
            start_day="2026-03-10",
            end_day="2026-03-20",
            products=[{"product_name": "A", "unit_price": 800.0}],
        ),
    ]
    
    print("\n" + "=" * 60)
    print("测试：refresh_state API 故障降级")
    print("=" * 60)
    
    try:
        state = state_mgr.refresh_state(
            api=api,
            today="2026-03-15",
            contracts=contracts,
            auto_init=True,
        )
        print("❌ 应该抛出异常")
        return False
    except Exception as e:
        print(f"✅ API 故障时正确抛出异常：{e}")
        print("=" * 60)
        return True
    finally:
        shutil.rmtree(test_state_dir, ignore_errors=True)


if __name__ == "__main__":
    test_refresh_state_auto_init()
    test_refresh_state_update_existing()
    test_refresh_state_no_api()
    print("\n🎉 所有测试完成！")
