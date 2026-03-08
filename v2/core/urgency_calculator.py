"""
urgency_calculator.py

合同紧急程度计算器

功能:
1. 计算单个合同的紧急度
2. 批量计算多个合同的紧急度
3. 支持自定义权重配置
4. 提供紧急度分级

使用方式:
    calculator = UrgencyCalculator()
    urgency = calculator.calculate(contract, today)
"""

from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class UrgencyConfig:
    """紧急度计算配置"""
    time_weight: float = 0.4        # 时间权重
    progress_weight: float = 0.3    # 进度权重
    quantity_weight: float = 0.2    # 数量权重
    risk_weight: float = 0.1        # 风险权重
    
    # 风险阈值
    high_risk_days: int = 3         # 高风险天数阈值
    medium_risk_days: int = 7       # 中风险天数阈值
    low_risk_days: int = 14         # 低风险天数阈值
    
    # 风险进度阈值
    high_risk_progress: float = 0.5   # 高风险进度阈值
    medium_risk_progress: float = 0.7 # 中风险进度阈值
    low_risk_progress: float = 0.9    # 低风险进度阈值
    
    def __post_init__(self):
        total = (self.time_weight + self.progress_weight + 
                self.quantity_weight + self.risk_weight)
        if abs(total - 1.0) > 0.01:
            raise ValueError(f"权重总和必须为 1.0，当前为{total}")


@dataclass
class UrgencyResult:
    """紧急度计算结果"""
    contract_id: str
    urgency_score: float          # 综合紧急度 (0-1)
    time_urgency: float           # 时间紧急度
    progress_urgency: float       # 进度紧急度
    quantity_urgency: float       # 数量紧急度
    risk_urgency: float           # 风险紧急度
    level: str                    # 紧急程度等级
    remaining_days: int           # 剩余天数
    progress: float               # 完成进度
    remaining_quantity: float     # 剩余量
    
    @property
    def is_urgent(self) -> bool:
        """是否紧急"""
        return self.urgency_score >= 0.7
    
    @property
    def is_critical(self) -> bool:
        """是否非常紧急"""
        return self.urgency_score >= 0.85


class UrgencyCalculator:
    """合同紧急度计算器"""
    
    def __init__(self, config: Optional[UrgencyConfig] = None):
        """
        初始化计算器
        
        参数:
            config: 计算配置，None 则使用默认配置
        """
        self.config = config or UrgencyConfig()
    
    def calculate(self, contract, today: int) -> UrgencyResult:
        """
        计算合同紧急度
        
        参数:
            contract: 合同对象（需要有 Q, start_day, end_day, delivered_so_far 属性）
            today: 今日（day 编号）
        
        返回:
            UrgencyResult: 紧急度计算结果
        """
        # 提取合同信息
        contract_id = getattr(contract, 'cid', 'UNKNOWN')
        total_qty = getattr(contract, 'Q', 0)
        start_day = getattr(contract, 'start_day', 0)
        end_day = getattr(contract, 'end_day', 0)
        delivered = getattr(contract, 'delivered_so_far', 0)
        
        # 计算基础数据
        total_days = end_day - start_day
        remaining_days = max(0, end_day - today)
        completed_qty = delivered
        remaining_qty = total_qty - completed_qty
        progress = completed_qty / total_qty if total_qty > 0 else 0
        
        # 计算各维度紧急度
        time_urgency = self._calc_time_urgency(remaining_days, total_days)
        progress_urgency = self._calc_progress_urgency(progress)
        quantity_urgency = self._calc_quantity_urgency(
            remaining_qty, remaining_days, total_qty, total_days
        )
        risk_urgency = self._calc_risk_urgency(
            remaining_days, progress
        )
        
        # 综合紧急度
        urgency_score = (
            self.config.time_weight * time_urgency +
            self.config.progress_weight * progress_urgency +
            self.config.quantity_weight * quantity_urgency +
            self.config.risk_weight * risk_urgency
        )
        
        # 紧急程度等级
        level = self._get_urgency_level(urgency_score)
        
        return UrgencyResult(
            contract_id=contract_id,
            urgency_score=urgency_score,
            time_urgency=time_urgency,
            progress_urgency=progress_urgency,
            quantity_urgency=quantity_urgency,
            risk_urgency=risk_urgency,
            level=level,
            remaining_days=remaining_days,
            progress=progress,
            remaining_quantity=remaining_qty,
        )
    
    def calculate_batch(self, contracts: List, today: int) -> List[UrgencyResult]:
        """
        批量计算合同紧急度
        
        参数:
            contracts: 合同列表
            today: 今日（day 编号）
        
        返回:
            紧急度结果列表（按紧急度降序排序）
        """
        results = [self.calculate(contract, today) for contract in contracts]
        
        # 按紧急度降序排序
        results.sort(key=lambda r: r.urgency_score, reverse=True)
        
        return results
    
    def _calc_time_urgency(self, remaining_days: int, total_days: int) -> float:
        """
        计算时间紧急度
        
        公式：1.0 - (remaining_days / total_days)
        """
        if total_days <= 0:
            return 1.0
        
        ratio = remaining_days / total_days
        return 1.0 - ratio
    
    def _calc_progress_urgency(self, progress: float) -> float:
        """
        计算进度紧急度
        
        公式：1.0 - progress
        """
        return 1.0 - progress
    
    def _calc_quantity_urgency(self, remaining_qty: float, remaining_days: int,
                               total_qty: float, total_days: int) -> float:
        """
        计算数量紧急度
        
        公式：min(daily_needed / daily_capacity, 1.0)
        """
        if remaining_days <= 0:
            return 1.0 if remaining_qty > 0 else 0.0
        
        if total_days <= 0:
            return 1.0
        
        daily_needed = remaining_qty / remaining_days
        daily_capacity = total_qty / total_days
        
        return min(daily_needed / daily_capacity, 1.0)
    
    def _calc_risk_urgency(self, remaining_days: int, progress: float) -> float:
        """
        计算风险紧急度
        
        综合考虑时间和进度，评估违约风险
        """
        # 高风险：时间紧 + 进度慢
        if (remaining_days < self.config.high_risk_days and 
            progress < self.config.high_risk_progress):
            return 1.0
        
        # 中风险
        if (remaining_days < self.config.medium_risk_days and 
            progress < self.config.medium_risk_progress):
            return 0.7
        
        # 低风险
        if (remaining_days < self.config.low_risk_days and 
            progress < self.config.low_risk_progress):
            return 0.3
        
        # 无风险
        return 0.0
    
    def _get_urgency_level(self, urgency_score: float) -> str:
        """获取紧急程度等级"""
        if urgency_score >= 0.85:
            return "非常紧急"
        elif urgency_score >= 0.7:
            return "紧急"
        elif urgency_score >= 0.5:
            return "中等"
        elif urgency_score >= 0.3:
            return "一般"
        else:
            return "不紧急"


# =========================
# 使用示例
# =========================

class MockContract:
    """模拟合同（用于测试）"""
    def __init__(self, cid, Q, start_day, end_day, delivered=0):
        self.cid = cid
        self.Q = Q
        self.start_day = start_day
        self.end_day = end_day
        self.delivered_so_far = delivered


if __name__ == "__main__":
    print("=" * 80)
    print("合同紧急度计算器示例")
    print("=" * 80)
    
    calculator = UrgencyCalculator()
    
    # 示例 1: 紧急合同
    print("\n1. 紧急合同示例")
    print("-" * 80)
    
    contract1 = MockContract(
        cid="HT-2026-001",
        Q=500,
        start_day=1,
        end_day=20,
        delivered=100  # 完成 20%
    )
    
    result = calculator.calculate(contract1, today=15)
    
    print(f"合同：{result.contract_id}")
    print(f"总量：500 吨，已完成：100 吨 ({result.progress:.1%})")
    print(f"有效期：Day 1-20，今日：Day 15，剩余：{result.remaining_days}天")
    print(f"\n紧急度得分：{result.urgency_score:.2f} ({result.level})")
    print(f"  - 时间紧急度：{result.time_urgency:.2f}")
    print(f"  - 进度紧急度：{result.progress_urgency:.2f}")
    print(f"  - 数量紧急度：{result.quantity_urgency:.2f}")
    print(f"  - 风险紧急度：{result.risk_urgency:.2f}")
    
    # 示例 2: 普通合同
    print("\n2. 普通合同示例")
    print("-" * 80)
    
    contract2 = MockContract(
        cid="HT-2026-002",
        Q=500,
        start_day=1,
        end_day=30,
        delivered=200  # 完成 40%
    )
    
    result = calculator.calculate(contract2, today=10)
    
    print(f"合同：{result.contract_id}")
    print(f"总量：500 吨，已完成：200 吨 ({result.progress:.1%})")
    print(f"有效期：Day 1-30，今日：Day 10，剩余：{result.remaining_days}天")
    print(f"\n紧急度得分：{result.urgency_score:.2f} ({result.level})")
    print(f"  - 时间紧急度：{result.time_urgency:.2f}")
    print(f"  - 进度紧急度：{result.progress_urgency:.2f}")
    print(f"  - 数量紧急度：{result.quantity_urgency:.2f}")
    print(f"  - 风险紧急度：{result.risk_urgency:.2f}")
    
    # 示例 3: 批量计算
    print("\n3. 批量计算示例")
    print("-" * 80)
    
    contracts = [
        MockContract("HT-001", 500, 1, 20, 100),
        MockContract("HT-002", 500, 1, 30, 200),
        MockContract("HT-003", 500, 1, 30, 300),
        MockContract("HT-004", 500, 1, 25, 400),
    ]
    
    results = calculator.calculate_batch(contracts, today=10)
    
    print(f"{'合同':<12} {'紧急度':>10} {'等级':>10} {'剩余天数':>10} {'进度':>10}")
    print("-" * 80)
    for r in results:
        print(f"{r.contract_id:<12} {r.urgency_score:>10.2f} {r.level:>10} "
              f"{r.remaining_days:>10} {r.progress:>10.1%}")
    
    print("\n" + "=" * 80)
    print("示例完成")
    print("=" * 80)
