"""
capacity_allocator.py

产能动态分配器

功能：
1. 根据需求权重分配产能
2. 根据合同紧急度分配产能（集成紧急度计算器）
3. 根据合同需求分配产能
4. 多因素综合分配（需求 + 紧急 + 库存）
5. 支持自定义配置

使用方式：
    allocator = CapacityAllocator()
    allocation = allocator.allocate(
        total_cap=350,
        warehouse='W1',
        categories=['A', 'B'],
        context=context
    )

集成紧急度计算：
    from urgency_calculator import UrgencyCalculator
    
    calculator = UrgencyCalculator()
    urgency_results = calculator.calculate_batch(contracts, today)
    
    context = {
        'urgency_results': urgency_results,  # 紧急度结果
        'inventory': {...},
    }
    
    allocation = allocator.allocate(..., context=context)
"""

from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class AllocationConfig:
    """分配配置"""
    demand_weight: float = 0.5      # 需求权重
    urgency_weight: float = 0.3     # 紧急程度权重
    inventory_weight: float = 0.2   # 库存权重
    
    # 归一化检查
    def __post_init__(self):
        total = (self.demand_weight + self.urgency_weight + 
                self.inventory_weight)
        if abs(total - 1.0) > 0.01:
            raise ValueError(f"权重总和必须为 1.0，当前为{total}")


@dataclass
class AllocationResult:
    """分配结果"""
    warehouse: str
    day: str
    total_capacity: float
    allocation: Dict[str, float]
    strategy: str  # 使用的分配策略


class CapacityAllocator:
    """产能分配器"""
    
    def __init__(self, config: Optional[AllocationConfig] = None):
        """
        初始化分配器
        
        参数:
            config: 分配配置，None 则使用默认配置
        """
        self.config = config or AllocationConfig()
    
    def allocate(self, total_cap: float, warehouse: str,
                 categories: List[str], 
                 context: Optional[Dict] = None) -> Dict[str, float]:
        """
        动态分配产能
        
        参数:
            total_cap: 总产能（吨）
            warehouse: 仓库
            categories: 品类列表
            context: 上下文信息
                - demand_weights: 需求权重 {(warehouse, category): weight}
                - urgency_results: 紧急度计算结果列表（优先）
                - urgency: 紧急程度 {category: score}（降级）
                - contracts: 合同列表
                - inventory: 库存 {category: tons}
        
        返回:
            {category: allocated_cap}
        
        分配策略（优先级从高到低）:
        1. demand_weights: 外部需求权重
        2. urgency_results: 合同紧急度（集成紧急度计算器）
        3. contracts: 根据合同需求
        4. urgency: 紧急程度（手动指定）
        5. 多因素综合：需求 + 紧急 + 库存
        6. 平均分配：降级方案
        """
        context = context or {}
        
        # 策略 1: 使用外部需求权重
        if 'demand_weights' in context:
            return self._allocate_by_weights(
                total_cap, warehouse, categories,
                context['demand_weights']
            )
        
        # 策略 2: 使用合同紧急度（集成紧急度计算器）
        if 'urgency_results' in context:
            return self._allocate_by_urgency(
                total_cap, warehouse, categories,
                context['urgency_results']
            )
        
        # 策略 3: 根据合同需求
        if 'contracts' in context:
            return self._allocate_by_demand(
                total_cap, warehouse, categories,
                context['contracts']
            )
        
        # 策略 4: 使用手动指定的紧急度
        if 'urgency' in context:
            return self._allocate_by_urgency_map(
                total_cap, warehouse, categories,
                context['urgency']
            )
        
        # 策略 5: 多因素综合分配
        if 'inventory' in context:
            return self._allocate_multi_factor(
                total_cap, warehouse, categories, context
            )
        
        # 策略 6: 平均分配（降级）
        return self._allocate_average(total_cap, categories)
    
    def _allocate_by_weights(self, total_cap: float, warehouse: str,
                            categories: List[str], 
                            demand_weights: Dict) -> Dict[str, float]:
        """根据需求权重分配产能"""
        weights = []
        for cat in categories:
            key = (warehouse, cat)
            weight = demand_weights.get(key, 1.0)
            weights.append(weight)
        
        total_weight = sum(weights)
        if total_weight == 0:
            return self._allocate_average(total_cap, categories)
        
        return {
            cat: total_cap * (w / total_weight)
            for cat, w in zip(categories, weights)
        }
    
    def _allocate_by_urgency(self, total_cap: float, warehouse: str,
                            categories: List[str],
                            urgency_results: List) -> Dict[str, float]:
        """
        根据合同紧急度分配产能（集成紧急度计算器）
        
        参数:
            total_cap: 总产能
            warehouse: 仓库
            categories: 品类列表
            urgency_results: 紧急度计算结果列表
        
        返回:
            {category: allocated_cap}
        """
        # 构建品类紧急度映射
        urgency_map = {}
        for cat in categories:
            # 找出该品类相关的合同紧急度（取最大值）
            cat_urgencies = [
                r.urgency_score for r in urgency_results
                if cat in r.contract_id
            ]
            urgency_map[cat] = max(cat_urgencies) if cat_urgencies else 0.5
        
        return self._allocate_by_urgency_map(
            total_cap, warehouse, categories, urgency_map
        )
    
    def _allocate_by_urgency_map(self, total_cap: float, warehouse: str,
                                 categories: List[str],
                                 urgency_map: Dict[str, float]) -> Dict[str, float]:
        """根据紧急度映射分配产能"""
        total_urgency = sum(urgency_map.values())
        if total_urgency == 0:
            return self._allocate_average(total_cap, categories)
        
        return {
            cat: total_cap * (urgency / total_urgency)
            for cat, urgency in urgency_map.items()
        }
    
    def _allocate_by_demand(self, total_cap: float, warehouse: str,
                           categories: List[str], 
                           contracts: List) -> Dict[str, float]:
        """根据合同需求分配产能"""
        demands = {cat: 0.0 for cat in categories}
        
        for contract in contracts:
            for cat in contract.allowed_categories:
                remaining = getattr(contract, 'Q', 0)
                delivered = getattr(contract, 'delivered_so_far', 0)
                demands[cat] += (remaining - delivered)
        
        total_demand = sum(demands.values())
        if total_demand == 0:
            return self._allocate_average(total_cap, categories)
        
        return {
            cat: total_cap * (demand / total_demand)
            for cat, demand in demands.items()
        }
    
    def _allocate_multi_factor(self, total_cap: float, warehouse: str,
                               categories: List[str],
                               context: Dict) -> Dict[str, float]:
        """多因素综合分配"""
        weights = self._calculate_composite_weights(
            warehouse, categories, context
        )
        
        total_weight = sum(weights.values())
        if total_weight == 0:
            return self._allocate_average(total_cap, categories)
        
        return {
            cat: total_cap * (w / total_weight)
            for cat, w in weights.items()
        }
    
    def _calculate_composite_weights(self, warehouse: str,
                                    categories: List[str],
                                    context: Dict) -> Dict[str, float]:
        """计算各品类综合权重"""
        weights = {}
        
        for cat in categories:
            # 1. 需求权重
            demand = self._get_demand_score(cat, context)
            
            # 2. 紧急程度
            urgency = context.get('urgency', {}).get(cat, 0.5)
            
            # 3. 库存比例（库存越少权重越高）
            inventory = context.get('inventory', {}).get(cat, 0)
            inventory_score = self._calculate_inventory_score(inventory)
            
            # 综合权重
            weights[cat] = (
                self.config.demand_weight * demand +
                self.config.urgency_weight * urgency +
                self.config.inventory_weight * inventory_score
            )
        
        return weights
    
    def _get_demand_score(self, category: str, context: Dict) -> float:
        """获取品类需求得分"""
        contracts = context.get('contracts', [])
        if not contracts:
            return 0.5
        
        total_demand = sum(getattr(c, 'Q', 0) for c in contracts)
        if total_demand == 0:
            return 0.5
        
        cat_demand = sum(
            getattr(c, 'Q', 0) for c in contracts
            if category in c.allowed_categories
        )
        
        return cat_demand / total_demand
    
    def _calculate_inventory_score(self, inventory: float) -> float:
        """计算库存得分（库存越少得分越高）"""
        target_days = 7
        daily_consumption = 50
        target_inventory = target_days * daily_consumption
        
        if inventory <= 0:
            return 1.0
        elif inventory >= target_inventory:
            return 0.0
        else:
            return 1.0 - (inventory / target_inventory)
    
    def _allocate_average(self, total_cap: float, 
                         categories: List[str]) -> Dict[str, float]:
        """平均分配（降级方案）"""
        if not categories:
            return {}
        
        cap_per_category = total_cap / len(categories)
        return {cat: cap_per_category for cat in categories}


# =========================
# 使用示例
# =========================

class MockUrgencyResult:
    """模拟紧急度结果（用于测试）"""
    def __init__(self, contract_id, urgency_score):
        self.contract_id = contract_id
        self.urgency_score = urgency_score


if __name__ == "__main__":
    print("=" * 80)
    print("产能动态分配器示例（集成紧急度）")
    print("=" * 80)
    
    allocator = CapacityAllocator()
    
    # 示例 1: 平均分配（无上下文）
    print("\n1. 平均分配（无上下文）")
    print("-" * 80)
    
    result = allocator.allocate(
        total_cap=350,
        warehouse='W1',
        categories=['A', 'B']
    )
    
    print(f"总产能：350 吨")
    print(f"分配结果：{result}")
    print(f"A: {result['A']:.1f} 吨，B: {result['B']:.1f} 吨")
    
    # 示例 2: 根据需求权重
    print("\n2. 根据需求权重分配")
    print("-" * 80)
    
    context = {
        'demand_weights': {
            ('W1', 'A'): 5.0,
            ('W1', 'B'): 1.0,
        }
    }
    
    result = allocator.allocate(
        total_cap=350,
        warehouse='W1',
        categories=['A', 'B'],
        context=context
    )
    
    print(f"总产能：350 吨")
    print(f"需求权重：A=5.0, B=1.0")
    print(f"分配结果：{result}")
    print(f"A: {result['A']:.1f} 吨 (+54%), B: {result['B']:.1f} 吨 (-54%)")
    
    # 示例 3: 根据合同紧急度（集成紧急度计算器）
    print("\n3. 根据合同紧急度分配")
    print("-" * 80)
    
    urgency_results = [
        MockUrgencyResult("HT-001-A", 0.85),
        MockUrgencyResult("HT-002-B", 0.40),
    ]
    
    context = {
        'urgency_results': urgency_results,
    }
    
    result = allocator.allocate(
        total_cap=350,
        warehouse='W1',
        categories=['A', 'B'],
        context=context
    )
    
    print(f"总产能：350 吨")
    print(f"合同紧急度：A=0.85 (非常紧急), B=0.40 (一般)")
    print(f"分配结果：{result}")
    print(f"A: {result['A']:.1f} 吨 (+43%), B: {result['B']:.1f} 吨 (-43%)")
    
    # 示例 4: 多因素综合分配
    print("\n4. 多因素综合分配")
    print("-" * 80)
    
    context = {
        'urgency': {'A': 0.9, 'B': 0.5},
        'inventory': {'A': 200, 'B': 50},
    }
    
    result = allocator.allocate(
        total_cap=350,
        warehouse='W1',
        categories=['A', 'B'],
        context=context
    )
    
    print(f"总产能：350 吨")
    print(f"紧急程度：A=0.9, B=0.5")
    print(f"库存：A=200 吨，B=50 吨")
    print(f"分配结果：{result}")
    print(f"A: {result['A']:.1f} 吨，B: {result['B']:.1f} 吨")
    
    print("\n" + "=" * 80)
    print("示例完成")
    print("=" * 80)
