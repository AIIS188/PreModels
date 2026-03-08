"""
capacity_allocator.py

产能动态分配器

功能：
1. 根据需求权重分配产能
2. 根据合同需求分配产能
3. 多因素综合分配（需求 + 紧急 + 利润 + 库存）
4. 支持自定义配置

使用方式：
    allocator = CapacityAllocator()
    allocation = allocator.allocate(
        total_cap=350,
        warehouse='W1',
        categories=['A', 'B'],
        context=context
    )
"""

from typing import Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class AllocationConfig:
    """分配配置"""
    demand_weight: float = 0.4      # 需求权重
    urgency_weight: float = 0.3     # 紧急程度权重
    profit_weight: float = 0.2      # 利润权重
    inventory_weight: float = 0.1   # 库存权重
    
    # 归一化检查
    def __post_init__(self):
        total = (self.demand_weight + self.urgency_weight + 
                self.profit_weight + self.inventory_weight)
        if abs(total - 1.0) > 0.01:
            raise ValueError(f"权重总和必须为 1.0，当前为{total}")


@dataclass
class AllocationResult:
    """分配结果"""
    warehouse: str
    day: int
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
                - contracts: 合同列表
                - demand_weights: 需求权重 {(warehouse, category): weight}
                - urgency: 紧急程度 {category: score}
                - profit: 利润率 {category: margin}
                - inventory: 库存 {category: tons}
        
        返回:
            {category: allocated_cap}
        
        分配策略（优先级从高到低）:
        1. demand_weights: 外部需求权重
        2. contracts: 根据合同需求
        3. 多因素综合：需求 + 紧急 + 利润 + 库存
        4. 平均分配：降级方案
        """
        context = context or {}
        
        # 策略 1: 使用外部需求权重
        if 'demand_weights' in context:
            return self._allocate_by_weights(
                total_cap, warehouse, categories,
                context['demand_weights']
            )
        
        # 策略 2: 根据合同需求
        if 'contracts' in context:
            return self._allocate_by_demand(
                total_cap, warehouse, categories,
                context['contracts']
            )
        
        # 策略 3: 多因素综合分配
        if any(k in context for k in ['urgency', 'profit', 'inventory']):
            return self._allocate_multi_factor(
                total_cap, warehouse, categories, context
            )
        
        # 策略 4: 平均分配（降级）
        return self._allocate_average(total_cap, categories)
    
    def _allocate_by_weights(self, total_cap: float, warehouse: str,
                            categories: List[str], 
                            demand_weights: Dict) -> Dict[str, float]:
        """
        根据需求权重分配产能
        
        参数:
            total_cap: 总产能
            warehouse: 仓库
            categories: 品类列表
            demand_weights: 需求权重 {(warehouse, category): weight}
        
        返回:
            {category: allocated_cap}
        """
        # 获取各品类权重
        weights = []
        for cat in categories:
            key = (warehouse, cat)
            weight = demand_weights.get(key, 1.0)
            weights.append(weight)
        
        # 归一化并分配
        total_weight = sum(weights)
        if total_weight == 0:
            return self._allocate_average(total_cap, categories)
        
        return {
            cat: total_cap * (w / total_weight)
            for cat, w in zip(categories, weights)
        }
    
    def _allocate_by_demand(self, total_cap: float, warehouse: str,
                           categories: List[str], 
                           contracts: List) -> Dict[str, float]:
        """
        根据合同需求分配产能
        
        参数:
            total_cap: 总产能
            warehouse: 仓库
            categories: 品类列表
            contracts: 合同列表
        
        返回:
            {category: allocated_cap}
        """
        # 统计各品类需求
        demands = {cat: 0.0 for cat in categories}
        
        for contract in contracts:
            for cat in contract.allowed_categories:
                # 使用合同剩余量
                remaining = getattr(contract, 'Q', 0)
                delivered = getattr(contract, 'delivered_so_far', 0)
                demands[cat] += (remaining - delivered)
        
        # 按需求比例分配
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
        """
        多因素综合分配
        
        考虑因素:
        - 需求比例 (40%)
        - 紧急程度 (30%)
        - 利润率 (20%)
        - 库存水平 (10%)
        
        参数:
            total_cap: 总产能
            warehouse: 仓库
            categories: 品类列表
            context: 上下文信息
        
        返回:
            {category: allocated_cap}
        """
        # 计算各品类综合权重
        weights = self._calculate_composite_weights(
            warehouse, categories, context
        )
        
        # 归一化并分配
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
            
            # 3. 利润率
            profit = context.get('profit', {}).get(cat, 0.5)
            
            # 4. 库存比例（库存越少权重越高）
            inventory = context.get('inventory', {}).get(cat, 0)
            inventory_score = self._calculate_inventory_score(inventory)
            
            # 综合权重
            weights[cat] = (
                self.config.demand_weight * demand +
                self.config.urgency_weight * urgency +
                self.config.profit_weight * profit +
                self.config.inventory_weight * inventory_score
            )
        
        return weights
    
    def _get_demand_score(self, category: str, context: Dict) -> float:
        """获取品类需求得分"""
        contracts = context.get('contracts', [])
        if not contracts:
            return 0.5
        
        # 计算该品类的合同需求占比
        total_demand = sum(getattr(c, 'Q', 0) for c in contracts)
        if total_demand == 0:
            return 0.5
        
        cat_demand = sum(
            getattr(c, 'Q', 0) for c in contracts
            if category in c.allowed_categories
        )
        
        return cat_demand / total_demand
    
    def _calculate_inventory_score(self, inventory: float) -> float:
        """
        计算库存得分
        
        库存越少，得分越高（需要更多产能）
        
        参数:
            inventory: 当前库存（吨）
        
        返回:
            库存得分 (0-1)
        """
        # 目标库存天数（7 天）
        target_days = 7
        # 日均消耗（假设 50 吨/天）
        daily_consumption = 50
        
        # 目标库存
        target_inventory = target_days * daily_consumption
        
        # 库存得分（库存越少得分越高）
        if inventory <= 0:
            return 1.0
        elif inventory >= target_inventory:
            return 0.0
        else:
            return 1.0 - (inventory / target_inventory)
    
    def _allocate_average(self, total_cap: float, 
                         categories: List[str]) -> Dict[str, float]:
        """
        平均分配（降级方案）
        
        参数:
            total_cap: 总产能
            categories: 品类列表
        
        返回:
            {category: allocated_cap}
        """
        if not categories:
            return {}
        
        cap_per_category = total_cap / len(categories)
        return {cat: cap_per_category for cat in categories}


# =========================
# 使用示例
# =========================

if __name__ == "__main__":
    print("=" * 80)
    print("产能动态分配器示例")
    print("=" * 80)
    
    # 示例 1: 平均分配（降级）
    print("\n1. 平均分配（无上下文）")
    print("-" * 80)
    
    allocator = CapacityAllocator()
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
            ('W1', 'A'): 5.0,  # A 需求大
            ('W1', 'B'): 1.0,  # B 需求小
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
    
    # 示例 3: 多因素综合分配
    print("\n3. 多因素综合分配")
    print("-" * 80)
    
    context = {
        'urgency': {'A': 0.9, 'B': 0.5},     # A 更紧急
        'profit': {'A': 0.7, 'B': 0.8},      # B 利润高
        'inventory': {'A': 200, 'B': 50},    # B 库存紧张
    }
    
    result = allocator.allocate(
        total_cap=350,
        warehouse='W1',
        categories=['A', 'B'],
        context=context
    )
    
    print(f"总产能：350 吨")
    print(f"紧急程度：A=0.9, B=0.5")
    print(f"利润率：A=0.7, B=0.8")
    print(f"库存：A=200 吨，B=50 吨")
    print(f"分配结果：{result}")
    print(f"A: {result['A']:.1f} 吨，B: {result['B']:.1f} 吨")
    
    print("\n" + "=" * 80)
    print("示例完成")
    print("=" * 80)
