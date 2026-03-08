#!/usr/bin/env python3
"""
run_daily_optimization.py

每日自动优化脚本

功能:
1. 自动获取当前日期
2. 运行滚动优化
3. 发送执行结果通知
4. 记录执行日志

使用方式:
    # 手动运行
    python3 run_daily_optimization.py --today auto
    
    # crontab 配置 (每日 08:00 运行)
    0 8 * * * cd /root/.openclaw/workspace/PreModels/scripts && python3 run_daily_optimization.py --today auto >> /var/log/premodels/daily_optimization.log 2>&1
"""

import sys
import os
import json
import argparse
import logging
from datetime import datetime
from pathlib import Path

# 添加 v2 目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent / "v2"))

from rolling_optimizer import RollingOptimizer
from state_manager import StateManager


# =========================
# 配置
# =========================

# 日志配置
LOG_DIR = Path("/var/log/premodels")
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / "daily_optimization.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("daily_optimization")


# =========================
# 通知配置
# =========================

class NotificationConfig:
    """通知配置"""
    # 启用通知
    enabled = True
    
    # 通知方式 (根据需要配置)
    email_enabled = False
    webhook_enabled = False
    
    # 收件人/地址
    email_recipients = ["admin@example.com"]
    webhook_url = ""


def send_notification(subject: str, message: str, success: bool):
    """
    发送通知
    
    参数:
        subject: 通知标题
        message: 通知内容
        success: 是否成功
    """
    if not NotificationConfig.enabled:
        logger.info(f"通知已禁用：{subject}")
        return
    
    # 邮件通知
    if NotificationConfig.email_enabled:
        try:
            send_email_notification(subject, message, NotificationConfig.email_recipients)
            logger.info("邮件通知已发送")
        except Exception as e:
            logger.error(f"邮件通知失败：{e}")
    
    # Webhook 通知
    if NotificationConfig.webhook_enabled:
        try:
            send_webhook_notification(subject, message, success, NotificationConfig.webhook_url)
            logger.info("Webhook 通知已发送")
        except Exception as e:
            logger.error(f"Webhook 通知失败：{e}")


def send_email_notification(subject: str, message: str, recipients: list):
    """发送邮件通知"""
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    
    # TODO: 配置 SMTP 服务器
    smtp_server = "smtp.example.com"
    smtp_port = 587
    smtp_user = "noreply@example.com"
    smtp_password = "password"
    
    msg = MIMEMultipart()
    msg['From'] = smtp_user
    msg['To'] = ", ".join(recipients)
    msg['Subject'] = subject
    
    msg.attach(MIMEText(message, 'plain'))
    
    server = smtplib.SMTP(smtp_server, smtp_port)
    server.starttls()
    server.login(smtp_user, smtp_password)
    server.send_message(msg)
    server.quit()


def send_webhook_notification(subject: str, message: str, success: bool, webhook_url: str):
    """发送 Webhook 通知"""
    import requests
    
    payload = {
        "title": subject,
        "content": message,
        "status": "success" if success else "failed",
        "timestamp": datetime.now().isoformat()
    }
    
    response = requests.post(webhook_url, json=payload, timeout=10)
    response.raise_for_status()


# =========================
# 优化执行
# =========================

def get_today_day_number() -> int:
    """
    获取当前的 day 编号
    
    计算从 2026-01-01 开始的天数
    """
    base = datetime(2026, 1, 1)
    today = datetime.now()
    delta = today - base
    return delta.days + 1


def run_optimization(today: int = None, H: int = 10) -> dict:
    """
    运行优化
    
    参数:
        today: 今日 (day 编号)，None 则自动计算
        H: 规划窗口（天数）
    
    返回:
        优化结果
    """
    logger.info(f"开始每日优化 (today={today}, H={H})")
    
    start_time = datetime.now()
    
    try:
        # 初始化优化器
        state_dir = Path(__file__).parent.parent / "v2" / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        
        optimizer = RollingOptimizer(
            state_dir=str(state_dir),
            api_base_url="http://127.0.0.1:8007",
        )
        
        # 运行优化
        result = optimizer.run(today=today, H=H)
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        logger.info(f"优化完成，耗时 {duration:.2f} 秒")
        
        # 统计结果
        stats = {
            "success": True,
            "today": today,
            "H": H,
            "shipments_count": len(result.get('x_today', {})),
            "total_tons": sum(result.get('x_today', {}).values()),
            "total_trucks": sum(result.get('trucks', {}).values()),
            "duration_seconds": duration,
            "timestamp": end_time.isoformat(),
        }
        
        # 发送成功通知
        send_notification(
            subject=f"✅ 每日优化成功 (Day {today})",
            message=f"""
每日优化执行成功

执行时间：{start_time.strftime('%Y-%m-%d %H:%M:%S')}
耗时：{duration:.2f} 秒

优化结果:
- 今日：Day {today}
- 发货计划：{stats['shipments_count']} 条
- 总吨数：{stats['total_tons']:.2f} 吨
- 总车数：{stats['total_trucks']} 车
- 平均载重：{stats['total_tons']/stats['total_trucks']:.1f} 吨/车
            """,
            success=True
        )
        
        return stats
        
    except Exception as e:
        logger.exception(f"优化失败：{e}")
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # 发送失败通知
        send_notification(
            subject=f"❌ 每日优化失败 (Day {today})",
            message=f"""
每日优化执行失败

执行时间：{start_time.strftime('%Y-%m-%d %H:%M:%S')}
错误信息：{str(e)}

请及时检查：
1. PD API 服务是否正常
2. 合同数据是否完整
3. 模型状态是否正常
            """,
            success=False
        )
        
        return {
            "success": False,
            "today": today,
            "error": str(e),
            "duration_seconds": duration,
            "timestamp": end_time.isoformat(),
        }


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="每日自动优化")
    parser.add_argument("--today", type=str, default="auto", 
                       help="今日 (day 编号)，auto=自动计算")
    parser.add_argument("--H", type=int, default=10, 
                       help="规划窗口（天数）")
    
    args = parser.parse_args()
    
    # 计算今日
    if args.today == "auto":
        today = get_today_day_number()
        logger.info(f"自动计算今日：Day {today}")
    else:
        today = int(args.today)
        logger.info(f"使用指定今日：Day {today}")
    
    # 运行优化
    result = run_optimization(today=today, H=args.H)
    
    # 保存执行记录
    record_file = LOG_DIR / "optimization_records.json"
    records = []
    if record_file.exists():
        with open(record_file, 'r', encoding='utf-8') as f:
            records = json.load(f)
    
    records.append(result)
    
    # 只保留最近 100 条记录
    records = records[-100:]
    
    with open(record_file, 'w', encoding='utf-8') as f:
        json.dump(records, f, indent=2, ensure_ascii=False, default=str)
    
    logger.info(f"执行记录已保存：{record_file}")
    
    # 返回状态码
    sys.exit(0 if result['success'] else 1)


if __name__ == "__main__":
    main()
