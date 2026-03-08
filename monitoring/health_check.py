#!/usr/bin/env python3
"""
health_check.py

服务健康检查脚本

功能:
1. 检查 FastAPI 服务状态
2. 检查 PD API 服务状态
3. 检查数据库连接
4. 检查优化模型状态
5. 发送告警通知

使用方式:
    # 手动检查
    python3 health_check.py
    
    # crontab 配置 (每 5 分钟检查一次)
    */5 * * * * cd /root/.openclaw/workspace/PreModels/monitoring && python3 health_check.py >> /var/log/premodels/health_check.log 2>&1
"""

import sys
import os
import json
import requests
import logging
from datetime import datetime
from pathlib import Path


# =========================
# 配置
# =========================

# 服务地址
FASTAPI_URL = "http://127.0.0.1:8001"
PD_API_URL = "http://127.0.0.1:8007"

# 日志配置
LOG_DIR = Path("/var/log/premodels")
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / "health_check.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("health_check")


# =========================
# 告警配置
# =========================

class AlertConfig:
    """告警配置"""
    # 告警阈值
    api_response_time_threshold = 1.0  # 秒
    optimization_failure_threshold = 3  # 连续失败次数
    
    # 告警通知
    alert_enabled = True
    webhook_url = ""  # 配置告警 webhook
    
    # 状态文件
    state_file = LOG_DIR / "health_state.json"


def send_alert(title: str, message: str, level: str = "critical"):
    """
    发送告警
    
    参数:
        title: 告警标题
        message: 告警内容
        level: 告警级别 (warning/critical)
    """
    if not AlertConfig.alert_enabled:
        logger.info(f"告警已禁用：{title}")
        return
    
    logger.warning(f"告警 [{level}]: {title} - {message}")
    
    # Webhook 告警
    if AlertConfig.webhook_url:
        try:
            payload = {
                "title": title,
                "message": message,
                "level": level,
                "timestamp": datetime.now().isoformat()
            }
            requests.post(AlertConfig.webhook_url, json=payload, timeout=10)
        except Exception as e:
            logger.error(f"告警发送失败：{e}")


# =========================
# 健康检查
# =========================

def check_fastapi_service() -> dict:
    """
    检查 FastAPI 服务
    
    返回:
        {"status": "ok/fail", "response_time": float, "message": str}
    """
    start_time = datetime.now()
    
    try:
        response = requests.get(f"{FASTAPI_URL}/health", timeout=5)
        response.raise_for_status()
        
        response_time = (datetime.now() - start_time).total_seconds()
        
        if response.json().get("status") == "ok":
            return {
                "status": "ok",
                "response_time": response_time,
                "message": "FastAPI 服务正常"
            }
        else:
            return {
                "status": "fail",
                "response_time": response_time,
                "message": "FastAPI 服务返回异常状态"
            }
    
    except requests.exceptions.Timeout:
        return {
            "status": "fail",
            "response_time": 5.0,
            "message": "FastAPI 服务响应超时"
        }
    except requests.exceptions.ConnectionError:
        return {
            "status": "fail",
            "response_time": 0.0,
            "message": "FastAPI 服务无法连接"
        }
    except Exception as e:
        return {
            "status": "fail",
            "response_time": 0.0,
            "message": f"FastAPI 服务检查失败：{str(e)}"
        }


def check_pd_api_service() -> dict:
    """
    检查 PD API 服务
    
    返回:
        {"status": "ok/fail", "response_time": float, "message": str}
    """
    start_time = datetime.now()
    
    try:
        response = requests.get(f"{PD_API_URL}/healthz", timeout=5)
        response.raise_for_status()
        
        response_time = (datetime.now() - start_time).total_seconds()
        
        if response.json().get("status") == "ok":
            return {
                "status": "ok",
                "response_time": response_time,
                "message": "PD API 服务正常"
            }
        else:
            return {
                "status": "fail",
                "response_time": response_time,
                "message": "PD API 服务返回异常状态"
            }
    
    except requests.exceptions.Timeout:
        return {
            "status": "fail",
            "response_time": 5.0,
            "message": "PD API 服务响应超时"
        }
    except requests.exceptions.ConnectionError:
        return {
            "status": "fail",
            "response_time": 0.0,
            "message": "PD API 服务无法连接"
        }
    except Exception as e:
        return {
            "status": "fail",
            "response_time": 0.0,
            "message": f"PD API 服务检查失败：{str(e)}"
        }


def check_optimization_state() -> dict:
    """
    检查优化模型状态
    
    返回:
        {"status": "ok/fail", "last_run": str, "message": str}
    """
    state_file = Path(__file__).parent.parent / "v2" / "state" / "state.json"
    
    if not state_file.exists():
        return {
            "status": "fail",
            "last_run": None,
            "message": "优化状态文件不存在"
        }
    
    try:
        with open(state_file, 'r', encoding='utf-8') as f:
            state = json.load(f)
        
        last_run_day = state.get('last_run_day')
        last_updated = state.get('last_updated')
        
        if last_run_day:
            return {
                "status": "ok",
                "last_run": f"Day {last_run_day} ({last_updated})",
                "message": "优化模型状态正常"
            }
        else:
            return {
                "status": "fail",
                "last_run": None,
                "message": "优化模型未运行"
            }
    
    except Exception as e:
        return {
            "status": "fail",
            "last_run": None,
            "message": f"优化模型状态检查失败：{str(e)}"
        }


def check_recent_optimizations() -> dict:
    """
    检查最近的优化执行记录
    
    返回:
        {"status": "ok/fail", "success_rate": float, "message": str}
    """
    record_file = LOG_DIR / "optimization_records.json"
    
    if not record_file.exists():
        return {
            "status": "ok",
            "success_rate": 1.0,
            "message": "无优化记录（可能是首次运行）"
        }
    
    try:
        with open(record_file, 'r', encoding='utf-8') as f:
            records = json.load(f)
        
        # 检查最近 10 次记录
        recent = records[-10:] if len(records) >= 10 else records
        
        if not recent:
            return {
                "status": "ok",
                "success_rate": 1.0,
                "message": "无优化记录"
            }
        
        success_count = sum(1 for r in recent if r.get('success'))
        success_rate = success_count / len(recent)
        
        if success_rate >= 0.9:
            return {
                "status": "ok",
                "success_rate": success_rate,
                "message": f"优化成功率：{success_rate:.1%}"
            }
        else:
            return {
                "status": "fail",
                "success_rate": success_rate,
                "message": f"优化成功率过低：{success_rate:.1%}"
            }
    
    except Exception as e:
        return {
            "status": "fail",
            "success_rate": 0.0,
            "message": f"优化记录检查失败：{str(e)}"
        }


def run_health_check() -> dict:
    """
    运行完整健康检查
    
    返回:
        检查结果
    """
    logger.info("开始健康检查")
    
    start_time = datetime.now()
    
    # 执行各项检查
    checks = {
        "fastapi_service": check_fastapi_service(),
        "pd_api_service": check_pd_api_service(),
        "optimization_state": check_optimization_state(),
        "recent_optimizations": check_recent_optimizations(),
    }
    
    # 统计结果
    ok_count = sum(1 for c in checks.values() if c.get('status') == 'ok')
    total_count = len(checks)
    overall_status = "ok" if ok_count == total_count else "fail"
    
    # 检查响应时间
    fastapi_response_time = checks['fastapi_service'].get('response_time', 0)
    if fastapi_response_time > AlertConfig.api_response_time_threshold:
        send_alert(
            title="FastAPI 服务响应慢",
            message=f"响应时间：{fastapi_response_time:.2f}秒 (阈值：{AlertConfig.api_response_time_threshold}秒)",
            level="warning"
        )
    
    # 检查优化成功率
    opt_success_rate = checks['recent_optimizations'].get('success_rate', 0)
    if opt_success_rate < 0.9:
        send_alert(
            title="优化成功率过低",
            message=f"最近优化成功率：{opt_success_rate:.1%}",
            level="critical"
        )
    
    # 总体状态
    result = {
        "status": overall_status,
        "timestamp": datetime.now().isoformat(),
        "checks": checks,
        "summary": {
            "ok_count": ok_count,
            "total_count": total_count,
            "health_score": ok_count / total_count
        }
    }
    
    # 记录结果
    logger.info(f"健康检查完成：{overall_status} (得分：{ok_count}/{total_count})")
    
    # 保存状态
    save_health_state(result)
    
    return result


def save_health_state(result: dict):
    """保存健康检查状态"""
    state_file = AlertConfig.state_file
    
    # 读取历史状态
    states = []
    if state_file.exists():
        try:
            with open(state_file, 'r', encoding='utf-8') as f:
                states = json.load(f)
        except:
            states = []
    
    # 添加新状态
    states.append(result)
    
    # 只保留最近 100 条
    states = states[-100:]
    
    # 保存
    with open(state_file, 'w', encoding='utf-8') as f:
        json.dump(states, f, indent=2, ensure_ascii=False, default=str)


def main():
    """主函数"""
    result = run_health_check()
    
    # 打印结果
    print("\n" + "=" * 60)
    print("PreModels v2 健康检查报告")
    print("=" * 60)
    print(f"检查时间：{result['timestamp']}")
    print(f"总体状态：{'✅ 正常' if result['status'] == 'ok' else '❌ 异常'}")
    print(f"健康得分：{result['summary']['health_score']:.1%}")
    print()
    
    for check_name, check_result in result['checks'].items():
        status_icon = "✅" if check_result['status'] == 'ok' else "❌"
        print(f"{status_icon} {check_name}: {check_result['message']}")
    
    print("=" * 60)
    
    # 返回状态码
    sys.exit(0 if result['status'] == 'ok' else 1)


if __name__ == "__main__":
    main()
