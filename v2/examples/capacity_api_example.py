#!/usr/bin/env python3
"""
capacity_api_example.py

产能预测 API 对接示例

展示如何实现外部产能预测模型与滚动优化器的对接

产能预测模型输出格式:
{
    "w1": [350, 360, 370, ...],  // w1 仓库未来每日总产能
    "w2": [200, 210, 220, ...],
    "w3": [150, 160, 170, ...]
}
"""

import requests
from typing import Dict, List, Optional


# =========================
# 方案 1: 直接调用产能预测 API
# =========================

class CapacityPredictorClient:
    """
    产能预测 API 客户端
    
    调用外部产能预测模型，获取未来 H 天的产能预测
    """
    
    def __init__(self, base_url: str = "http://capacity-predictor:8002"):
        self.base_url = base_url
    
    def predict_capacity(self, today: int, H: int) -> Optional[Dict]:
        """
        获取产能预测
        
        参数:
            today: 今日（day 编号）
            H: 预测天数
        
        返回:
            {
                "w1": [350, 360, 370, ...],  // H 天的产能
                "w2": [200, 210, 220, ...],
                "w3": [150, 160, 170, ...]
            }
        """
        try:
            response = requests.post(
                f"{self.base_url}/predict",
                json={
                    "today": today,
                    "H": H,
                },
                timeout=30
            )
            response.raise_for_status()
            
            result = response.json()
            
            # 验证返回格式
            if not self._validate_format(result, H):
                raise ValueError(f"产能预测返回格式错误：{result}")
            
            return result
            
        except Exception as e:
            print(f"产能预测 API 调用失败：{e}")
            return None
    
    def _validate_format(self, data: Dict, H: int) -> bool:
        """
        验证返回数据格式
        
        要求:
        - 是字典
        - 每个值是长度为 H 的数组
        - 数组元素是数字
        """
        if not isinstance(data, dict):
            return False
        
        for warehouse, caps in data.items():
            if not isinstance(caps, list):
                return False
            if len(caps) < H:
                return False
            if not all(isinstance(c, (int, float)) for c in caps):
                return False
        
        return True


# =========================
# 方案 2: 从文件读取（测试用）
# =========================

def load_capacity_from_file(file_path: str, H: int) -> Optional[Dict]:
    """
    从 JSON 文件读取产能预测（测试用）
    
    文件格式:
    {
        "w1": [350, 360, 370, 380, 390, 400, 350, 360, 370, 380],
        "w2": [200, 210, 220, 230, 240, 250, 200, 210, 220, 230],
        "w3": [150, 160, 170, 180, 190, 200, 150, 160, 170, 180]
    }
    
    参数:
        file_path: JSON 文件路径
        H: 需要的天数
    
    返回:
        产能预测字典
    """
    import json
    from pathlib import Path
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 截取前 H 天
        result = {}
        for warehouse, caps in data.items():
            result[warehouse] = caps[:H]
        
        return result
        
    except Exception as e:
        print(f"读取产能预测文件失败：{e}")
        return None


# =========================
# 方案 3: 集成到滚动优化器
# =========================

def integrate_with_rolling_optimizer():
    """
    演示如何将产能预测集成到滚动优化器
    
    修改 rolling_optimizer.py 中的 _load_capacity_from_api 方法
    """
    
    # 示例代码:
    """
    def _load_capacity_from_api(self, today: int, H: int) -> Optional[Dict]:
        # 方法 1: 调用外部 API
        client = CapacityPredictorClient(base_url="http://capacity-predictor:8002")
        capacity_data = client.predict_capacity(today, H)
        
        if capacity_data:
            # 转换为模型需要的格式
            categories = ["A", "B"]  # 从合同或配置获取
            return self._convert_capacity_format(capacity_data, today, H, categories)
        
        # 方法 2: 从文件读取（测试用）
        # capacity_data = load_capacity_from_file("./capacity_forecast.json", H)
        # if capacity_data:
        #     categories = ["A", "B"]
        #     return self._convert_capacity_format(capacity_data, today, H, categories)
        
        return None  # 返回 None 表示使用默认配置
    """
    pass


# =========================
# 使用示例
# =========================

if __name__ == "__main__":
    print("=" * 80)
    print("产能预测 API 对接示例")
    print("=" * 80)
    
    # 示例 1: 调用外部 API
    print("\n1. 调用外部产能预测 API")
    print("-" * 80)
    
    client = CapacityPredictorClient(base_url="http://capacity-predictor:8002")
    capacity = client.predict_capacity(today=10, H=10)
    
    if capacity:
        print(f"获取到产能预测数据:")
        for warehouse, caps in capacity.items():
            print(f"  {warehouse}: {caps}")
    else:
        print("API 调用失败，使用默认配置")
    
    # 示例 2: 从文件读取
    print("\n2. 从文件读取产能预测")
    print("-" * 80)
    
    # 创建示例文件
    import json
    from pathlib import Path
    
    example_file = Path("./capacity_forecast_example.json")
    example_data = {
        "w1": [350, 360, 370, 380, 390, 400, 350, 360, 370, 380],
        "w2": [200, 210, 220, 230, 240, 250, 200, 210, 220, 230],
        "w3": [150, 160, 170, 180, 190, 200, 150, 160, 170, 180]
    }
    
    with open(example_file, 'w', encoding='utf-8') as f:
        json.dump(example_data, f, indent=2)
    
    print(f"创建示例文件：{example_file}")
    print(f"内容：{json.dumps(example_data, indent=2)}")
    
    # 读取文件
    capacity = load_capacity_from_file(str(example_file), H=10)
    
    if capacity:
        print(f"\n读取成功:")
        for warehouse, caps in capacity.items():
            print(f"  {warehouse}: {caps}")
    
    # 示例 3: 格式转换
    print("\n3. 格式转换示例")
    print("-" * 80)
    
    # 模拟 API 返回
    capacity_data = {
        "w1": [350, 360, 370],
        "w2": [200, 210, 220],
    }
    
    # 转换为模型需要的格式
    from rolling_optimizer import RollingOptimizer
    
    optimizer = RollingOptimizer()
    categories = ["A", "B"]
    
    cap_forecast = optimizer._convert_capacity_format(
        capacity_data, 
        today=10, 
        H=3,
        categories=categories
    )
    
    print(f"输入格式 (API):")
    print(f"  {capacity_data}")
    
    print(f"\n输出格式 (模型):")
    for key, value in sorted(cap_forecast.items()):
        print(f"  {key}: {value:.1f} 吨")
    
    print("\n" + "=" * 80)
    print("示例完成")
    print("=" * 80)
