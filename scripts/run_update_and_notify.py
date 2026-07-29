#!/usr/bin/env python3
"""
中证红利定投策略看板：更新数据并推送飞书机器人通知。

使用方式：
1. 先配置环境变量：
   - DASHBOARD_PUBLIC_URL：稳定看板链接
   - FEISHU_CHAT_ID：飞书群 chat_id，形如 oc_xxx
   或：
   - FEISHU_USER_ID：飞书用户 open_id，形如 ou_xxx
2. 运行：
   python3 /workspace/csi-dividend-dca-dashboard/scripts/run_update_and_notify.py

说明：
- 不创建新的交付物。
- 只更新固定看板入口 index.html 和 assets/market_data.json。
- 如果未配置 FEISHU_CHAT_ID / FEISHU_USER_ID，则跳过飞书通知。
"""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path


BASE_DIR = Path("/workspace/csi-dividend-dca-dashboard")
UPDATE_SCRIPT = BASE_DIR / "scripts" / "update_data.py"
DATA_PATH = BASE_DIR / "assets" / "market_data.json"


def run_update():
    result = subprocess.run(
        [sys.executable, str(UPDATE_SCRIPT)],
        cwd=str(BASE_DIR),
        text=True,
        capture_output=True,
        timeout=180,
    )
    print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    if result.returncode != 0:
        raise RuntimeError(f"数据更新失败，退出码：{result.returncode}")


def load_market_data():
    with DATA_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def latest_record(data):
    records = data.get("feishu_records") or []
    return records[-1] if records else {}


def compose_message(data):
    meta = data.get("meta") or {}
    valuation = (data.get("index_valuation") or {}).get("csi_dividend") or {}
    technical = data.get("technical") or {}
    strategy = data.get("strategy_advice") or {}
    composite = strategy.get("composite_advice") or {}
    record = latest_record(data)

    dashboard_url = os.environ.get(
        "DASHBOARD_PUBLIC_URL",
        "https://qing-leee.github.io/csi-dividend-dashboard/",
    ).strip()
    period = meta.get("period_label", "更新")
    update_time = meta.get("update_time") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = [
        f"中证红利定投策略看板已更新（{period}版）",
        "",
        f"更新时间：{update_time}",
        f"外部数据截至：{meta.get('market_date', '--')}",
        "",
        f"累计投入：¥{record.get('cum_invest', 0):,.0f}",
        f"持有市值：¥{record.get('mkt_value', 0):,.2f}",
        f"累计收益率：{record.get('cum_return_pct', 0):+.2f}%",
        f"浮盈/亏：¥{record.get('pnl', 0):+,.2f}",
        "",
        f"PE2：{valuation.get('pe2', '--')}",
        f"D/P2：{valuation.get('div_yield2', '--')}%",
        f"RSI24：{technical.get('rsi24', '--')}",
        f"股债利差：{strategy.get('spread', '--')}%",
        f"综合建议：{composite.get('action', '--')}",
        f"建议说明：{composite.get('detail', '--')}",
    ]

    if dashboard_url:
        lines.extend(["", f"查看看板：{dashboard_url}"])
    else:
        lines.extend(["", "查看看板：待配置稳定站点链接"])

    return "\n".join(lines)


def send_feishu_message(message):
    chat_id = os.environ.get("FEISHU_CHAT_ID", "").strip()
    user_id = os.environ.get("FEISHU_USER_ID", "ou_708e2ec56f21772a6caab9cbe1c4d364").strip()

    if not chat_id and not user_id:
        print("[Feishu] 未配置 FEISHU_CHAT_ID 或 FEISHU_USER_ID，跳过通知")
        print("[Feishu] 消息预览：")
        print(message)
        return

    cmd = ["lark-cli", "im", "+messages-send", "--as", "user", "--text", message]
    if chat_id:
        cmd.extend(["--chat-id", chat_id])
    else:
        cmd.extend(["--user-id", user_id])

    result = subprocess.run(
        cmd,
        text=True,
        capture_output=True,
        timeout=60,
    )
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    if result.returncode != 0:
        raise RuntimeError(f"飞书通知发送失败，退出码：{result.returncode}")
    print("[Feishu] 通知已发送")


def push_to_github():
    """将更新后的 index.html 和 market_data.json 推送到 GitHub Pages"""
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not token:
        print("[Git] 未配置 GITHUB_TOKEN 环境变量，跳过推送")
        print("[Git] 请设置: export GITHUB_TOKEN='ghp_xxx'")
        return

    print("[Git] 开始推送更新到 GitHub...")
    remote_url = f"https://x-access-token:{token}@github.com/Qing-Leee/csi-dividend-dashboard.git"

    cmds = [
        ["git", "add", "index.html", "assets/market_data.json"],
        ["git", "commit", "-m", f"chore: auto-update dashboard data {datetime.now().strftime('%Y-%m-%d %H:%M')}"],
        ["git", "push", remote_url, "main"],
    ]

    for cmd in cmds:
        result = subprocess.run(cmd, cwd=str(BASE_DIR), text=True, capture_output=True, timeout=60)
        if result.stdout.strip():
            print(f"[Git] {result.stdout.strip()}")
        if result.returncode != 0 and "nothing to commit" not in (result.stdout + result.stderr):
            print(f"[Git] WARN: {result.stderr.strip()}")
    print("[Git] 推送完成")


def main():
    print("=" * 60)
    print("中证红利定投策略看板：更新 + 飞书通知")
    print("=" * 60)
    run_update()
    push_to_github()
    data = load_market_data()
    message = compose_message(data)
    send_feishu_message(message)
    print("=" * 60)
    print("[DONE] 固定看板已更新并推送")
    print("=" * 60)


if __name__ == "__main__":
    main()
