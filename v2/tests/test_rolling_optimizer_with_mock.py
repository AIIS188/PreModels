"""
test_rolling_optimizer_with_mock.py

使用模拟数据测试 RollingOptimizer 和复杂优化模型

功能：
1. 创建模拟的 PD API（返回测试数据）
2. 创建合理的测试场景（多个合同、在途、磅单等）
3. 运行 rolling_optimizer
4. 验证结果并生成性能报告

测试场景：
- 3 个有效合同（不同阶段）
- 2 个过期合同（测试清理逻辑）
- 多个在途报单（部分已过磅）
- 产能约束
- 多日规划窗口（H=10）
"""

import sys
from pathlib import Path
from unittest.mock import Mock
from dataclasses import dataclass
from typing import List, Dict, Optional
import json
import shutil

# 添加 v2 目录到路径（支持从 tests 目录运行）
v2_dir = Path(__file__).parent.parent
if str(v2_dir) not in sys.path:
    sys.path.insert(0, str(v2_dir))

from models.rolling_optimizer import RollingOptimizer
from models.common_utils_v2 import Contract
from core.date_utils import DateUtils


# =========================
# 模拟数据结构
# =========================

@dataclass
class MockWeighbill:
    """模拟磅单数据"""
    id: int
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
    has_delivery_order: str = "有"
    upload_status: str = "已上传"


# =========================
# 模拟 PD API
# =========================

class MockPDAPIClient:
    """
    模拟 PD API 客户端
    
    返回预设的测试数据，用于验证系统功能
    """
    
    def __init__(self, base_url: str = "http://mock"):
        self.base_url = base_url
        self.today = "2026-03-15"  # 测试基准日期
        
    def set_today(self, today: str):
        """设置测试基准日期"""
        self.today = today
    
    def get_contracts(self, page: int = 1, page_size: int = 100) -> List:
        """
        获取合同列表
        
        返回 5 个合同：
        - HT-001: 执行中（完成 60%）
        - HT-002: 刚启动（完成 0%）
        - HT-003: 即将到期（完成 80%）
        - HT-OLD-001: 已过期（测试清理）
        - HT-OLD-002: 已过期（测试清理）
        """
        return [
            # 有效合同
            type('Contract', (), {
                'contract_no': 'HT-001',
                'smelter_company': 'R1',
                'total_quantity': 1000.0,
                'contract_date': '2026-03-01',
                'end_date': '2026-03-25',
                'products': [{'product_name': 'A', 'unit_price': 800.0}],
            })(),
            
            type('Contract', (), {
                'contract_no': 'HT-002',
                'smelter_company': 'R1',
                'total_quantity': 800.0,
                'contract_date': '2026-03-10',
                'end_date': '2026-03-30',
                'products': [{'product_name': 'A', 'unit_price': 820.0}],
            })(),
            
            type('Contract', (), {
                'contract_no': 'HT-003',
                'smelter_company': 'R2',
                'total_quantity': 500.0,
                'contract_date': '2026-03-05',
                'end_date': '2026-03-18',  # 即将到期（还剩 3 天）
                'products': [{'product_name': 'A', 'unit_price': 790.0}],
            })(),
            
            # 过期合同（测试清理逻辑）
            type('Contract', (), {
                'contract_no': 'HT-OLD-001',
                'smelter_company': 'R1',
                'total_quantity': 600.0,
                'contract_date': '2026-02-01',
                'end_date': '2026-03-10',  # 已过期 5 天
                'products': [{'product_name': 'A', 'unit_price': 750.0}],
            })(),
            
            type('Contract', (), {
                'contract_no': 'HT-OLD-002',
                'smelter_company': 'R2',
                'total_quantity': 400.0,
                'contract_date': '2026-02-15',
                'end_date': '2026-03-14',  # 已过期 1 天
                'products': [{'product_name': 'A', 'unit_price': 760.0}],
            })(),
        ]
    
    def get_weighbills_today(self, today: str, cid: Optional[str] = None) -> List:
        """
        获取今日磅单
        
        模拟今日已过磅数据
        """
        # 今日已过磅：HT-001 (2 车), HT-002 (1 车)
        return [
            MockWeighbill(id=101, contract_no='HT-001', net_weight=35.2, weigh_time=f'{today} 08:30', vehicle_no='京 A12345'),
            MockWeighbill(id=102, contract_no='HT-001', net_weight=34.8, weigh_time=f'{today} 09:15', vehicle_no='京 B67890'),
            MockWeighbill(id=103, contract_no='HT-002', net_weight=35.5, weigh_time=f'{today} 10:00', vehicle_no='京 C11111'),
        ]
    
    def get_deliveries(self, exact_status: Optional[str] = None, **kwargs) -> List:
        """
        获取报货单列表
        
        模拟在途报单（待确认状态）
        """
        # 在途报单场景：
        # - HT-001: 3 单在途（1 单今日已过磅）
        # - HT-002: 2 单在途
        # - HT-003: 2 单在途（紧急，即将到期）
        # - HT-OLD-001: 1 单在途（应被清理）
        
        all_deliveries = [
            # HT-001 在途（3 单）
            MockDelivery(id=201, report_date='2026-03-14', contract_no='HT-001', warehouse='W1', target_factory_name='W1', product_name='A', quantity=35.0, vehicle_no='京 A12345'),  # 已过磅
            MockDelivery(id=202, report_date='2026-03-15', contract_no='HT-001', warehouse='W1', target_factory_name='W1', product_name='A', quantity=34.0, vehicle_no='京 D22222'),  # 未过磅
            MockDelivery(id=203, report_date='2026-03-15', contract_no='HT-001', warehouse='W2', target_factory_name='W2', product_name='A', quantity=36.0, vehicle_no='京 E33333'),  # 未过磅
            
            # HT-002 在途（2 单）
            MockDelivery(id=204, report_date='2026-03-15', contract_no='HT-002', warehouse='W1', target_factory_name='W1', product_name='A', quantity=33.0, vehicle_no='京 C11111'),  # 今日已磅
            MockDelivery(id=205, report_date='2026-03-15', contract_no='HT-002', warehouse='W2', target_factory_name='W2', product_name='A', quantity=35.0, vehicle_no='京 F44444'),  # 未过磅
            
            # HT-003 在途（2 单，紧急）
            MockDelivery(id=206, report_date='2026-03-14', contract_no='HT-003', warehouse='W1', target_factory_name='W1', product_name='A', quantity=34.0, vehicle_no='京 G55555'),
            MockDelivery(id=207, report_date='2026-03-15', contract_no='HT-003', warehouse='W2', target_factory_name='W2', product_name='A', quantity=35.0, vehicle_no='京 H66666'),
            
            # HT-OLD-001 在途（1 单，应被清理）
            MockDelivery(id=208, report_date='2026-03-13', contract_no='HT-OLD-001', warehouse='W1', target_factory_name='W1', product_name='A', quantity=33.0, vehicle_no='京 I77777'),
        ]
        
        # 如果指定了 exact_status="待确认"，返回全部（模拟都是待确认状态）
        if exact_status == '待确认':
            return all_deliveries
        
        # 否则按日期过滤
        exact_report_date = kwargs.get('exact_report_date')
        if exact_report_date:
            return [d for d in all_deliveries if d.report_date == exact_report_date]
        
        return all_deliveries


# =========================
# 测试运行器
# =========================

class MockRollingOptimizer(RollingOptimizer):
    """
    使用模拟 API 的 RollingOptimizer
    """
    
    def __init__(self, state_dir: str = "./state_test", api_base_url: str = "http://mock"):
        self.state_dir = state_dir
        self.api = MockPDAPIClient(api_base_url)
        
        # 手动导入 StateManager
        from core.state_manager import StateManager
        self.state_mgr = StateManager(state_dir)
    
    def _load_cap_forecast(self, today: str, H: int) -> Dict:
        """
        加载模拟产能预测
        
        返回合理的产能数据
        """
        cap_forecast = {}
        
        # 仓库发货能力（吨/天）
        capacity = {
            ("W1", "A"): 200.0,
            ("W2", "A"): 180.0,
        }
        
        # 生成 H 天的产能
        for d in range(H):
            date = DateUtils.add_days(today, d)
            for (w, k), base in capacity.items():
                # 工作日稍高，周末稍低
                dow = DateUtils.parse(date).weekday()
                factor = 1.0 if dow < 5 else 0.8
                cap_forecast[(w, k, date)] = base * factor
        
        return cap_forecast
    
    def _load_weight_profile(self) -> Dict:
        """加载估重画像"""
        return {
            ("W1", "R1", "A"): (35.0, 37.0),
            ("W1", "R2", "A"): (34.0, 36.0),
            ("W2", "R1", "A"): (35.0, 37.0),
            ("W2", "R2", "A"): (34.0, 36.0),
        }
    
    def _load_delay_profile(self) -> Dict:
        """加载延迟分布"""
        delay_dist = {0: 0.03, 1: 0.95, 2: 0.02}
        return {
            ("W1", "R1"): delay_dist,
            ("W1", "R2"): delay_dist,
            ("W2", "R1"): delay_dist,
            ("W2", "R2"): delay_dist,
        }


# =========================
# 测试执行
# =========================

def run_test():
    """运行完整测试"""
    
    print("=" * 80)
    print("RollingOptimizer 性能测试 - 模拟数据")
    print("=" * 80)
    
    # 准备测试环境
    test_state_dir = "./state_test_rolling"
    shutil.rmtree(test_state_dir, ignore_errors=True)
    
    # 创建优化器
    optimizer = MockRollingOptimizer(state_dir=test_state_dir)
    
    # 设置测试日期
    today = "2026-03-15"
    H = 10  # 规划窗口 10 天
    
    print(f"\n测试配置:")
    print(f"  - 基准日期：{today}")
    print(f"  - 规划窗口：H={H} 天")
    print(f"  - 状态目录：{test_state_dir}")
    
    # 运行优化
    print(f"\n{'='*80}")
    print("开始运行滚动优化...")
    print(f"{'='*80}\n")
    
    try:
        # 先检查合同加载
        contracts = optimizer._load_contracts()
        print(f"\n加载合同：{len(contracts)} 个")
        for c in contracts:
            print(f"  - {c.cid}: Q={c.Q}, end={c.end_day}, allowed={c.allowed_categories}")
        
        # 检查在途报单
        from core.api_client import get_in_transit_orders, get_weighed_truck_ids, filter_confirmed_arrivals
        in_transit = get_in_transit_orders(optimizer.api, today)
        print(f"\n在途报单：{len(in_transit)} 单")
        for o in in_transit:
            print(f"  - {o['order_id']} ({o['cid']}) w={o['warehouse']} k={o['category']} truck={o['truck_id']}")
        
        # 获取仓库和品类列表
        warehouses = list(set(o["warehouse"] for o in in_transit))
        categories = list(set(o["category"] for o in in_transit))
        print(f"\n仓库列表：{warehouses}")
        print(f"品类列表：{categories}")
        
        # 检查合同剩余量
        print(f"\n合同剩余量分析:")
        for c in contracts:
            if c.end_day < today:
                print(f"  - {c.cid}: 已过期 (end={c.end_day})")
                continue
            
            delivered = 70.0 if c.cid == 'HT-001' else (35.5 if c.cid == 'HT-002' else 0.0)
            remaining = 0.95 * c.Q - delivered
            days_left = DateUtils.diff_days(today, c.end_day) + 1
            daily_target = remaining / days_left if days_left > 0 else 0
            print(f"  - {c.cid}: 已到货={delivered:.1f}, 剩余={remaining:.1f}吨/{days_left}天，日均={daily_target:.1f}吨")
        
        result = optimizer.run(today_date=today, H=H)
        
        # 输出结果
        print(f"\n{'='*80}")
        print("优化结果")
        print(f"{'='*80}")
        
        # 今日发货计划
        print(f"\n1. 今日发货计划 ({len(result['x_today'])} 条):")
        for key, tons in sorted(result['x_today'].items()):
            print(f"   {key}: {tons:.2f} 吨")
        
        # 车数建议
        print(f"\n2. 车数建议 ({len(result['trucks'])} 条):")
        for key, trucks in sorted(result['trucks'].items()):
            print(f"   {key}: {trucks} 车")
        
        # 到货诊断
        print(f"\n3. 到货诊断 ({len(result['arrival_plan'])} 条):")
        for key, tons in sorted(result['arrival_plan'].items())[:10]:  # 只显示前 10 条
            print(f"   {key}: {tons:.2f} 吨")
        if len(result['arrival_plan']) > 10:
            print(f"   ... 共 {len(result['arrival_plan'])} 条")
        
        # 验证结果
        print(f"\n{'='*80}")
        print("结果验证")
        print(f"{'='*80}")
        
        # 检查今日是否有发货计划
        if len(result['x_today']) > 0:
            total_tons = sum(result['x_today'].values())
            print(f"✅ 今日有发货计划：总计 {total_tons:.2f} 吨")
        else:
            print(f"❌ 今日无发货计划（可能产能不足或合同已过期）")
        
        # 检查过期合同是否被清理
        state = optimizer.state_mgr.load_state()
        if state:
            print(f"\n状态检查:")
            print(f"  - delivered_so_far: {len(state.delivered_so_far)} 个合同")
            for cid, tons in sorted(state.delivered_so_far.items()):
                print(f"    {cid}: {tons:.2f} 吨")
            
            print(f"  - in_transit_orders: {len(state.in_transit_orders)} 单")
            
            # 检查过期合同是否被清理
            if 'HT-OLD-001' not in state.delivered_so_far and 'HT-OLD-002' not in state.delivered_so_far:
                print(f"✅ 过期合同已正确清理")
            else:
                print(f"❌ 过期合同未被清理")
            
            # 检查在途报单
            in_transit_cids = {o['cid'] for o in state.in_transit_orders}
            if 'HT-OLD-001' not in in_transit_cids:
                print(f"✅ 过期合同的在途报单已正确清理")
            else:
                print(f"❌ 过期合同的在途报单未被清理")
        
        # 生成报告
        print(f"\n{'='*80}")
        print("测试报告")
        print(f"{'='*80}")
        
        report = {
            "test_date": today,
            "planning_horizon": H,
            "results": {
                "shipments_today": len(result['x_today']),
                "total_tons_today": sum(result['x_today'].values()) if result['x_today'] else 0,
                "trucks_today": len(result['trucks']),
                "arrival_plan_entries": len(result['arrival_plan']),
            },
            "state": {
                "contracts_count": len(state.delivered_so_far) if state else 0,
                "in_transit_count": len(state.in_transit_orders) if state else 0,
            },
            "validation": {
                "has_shipments": len(result['x_today']) > 0,
                "expired_cleaned": 'HT-OLD-001' not in state.delivered_so_far if state else False,
                "expired_transit_cleaned": 'HT-OLD-001' not in in_transit_cids if state else False,
            }
        }
        
        print(json.dumps(report, indent=2, ensure_ascii=False))
        
        # 保存报告
        report_file = Path(test_state_dir) / "test_report.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"\n报告已保存到：{report_file}")
        
        print(f"\n{'='*80}")
        print("✅ 测试完成！")
        print(f"{'='*80}\n")
        
        return report
        
    except Exception as e:
        print(f"\n❌ 测试失败：{e}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        # 清理测试环境（可选）
        # shutil.rmtree(test_state_dir, ignore_errors=True)
        pass


if __name__ == "__main__":
    report = run_test()
    
    if report and report['validation']['has_shipments']:
        print("🎉 RollingOptimizer 功能正常！")
        sys.exit(0)
    else:
        print("⚠️  测试发现问题，请检查日志")
        sys.exit(1)
