#!/usr/bin/env python3
"""
中证红利定投策略看板：更新数据并输出小结。

使用方式：
1. 配置环境变量（可选）：
   - DASHBOARD_PUBLIC_URL：稳定看板链接
2. 在项目根目录运行：
   python3 scripts/run_update_and_notify.py

说明：
- 不创建新的交付物。
- 只更新固定看板入口 index.html 和 assets/market_data.json。
- 运行完成后输出数据小结和看板链接，可直接点击查看。
"""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
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


def compose_summary(data):
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
        lines.extend(["", f"看板链接：{dashboard_url}"])
    else:
        lines.extend(["", "看板链接：待配置 DASHBOARD_PUBLIC_URL"])

    return "\n".join(lines)


def push_to_github():
    """将更新后的 index.html 和 market_data.json 推送到 GitHub Pages"""
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not token:
        print("[Git] 未配置 GITHUB_TOKEN 环境变量，跳过推送")
        print("[Git] 请设置: export GITHUB_TOKEN='ghp_xxx'")
        return

    print("[Git] 开始推送更新到 GitHub...")
    remote_url = f"https://x-access-token:{token}@github.com/Qing-Leee/csi-dividend-dashboard.git"

    setup_cmds = [
        ["git", "config", "user.name", "Dashboard Auto Update"],
        ["git", "config", "user.email", "dashboard-auto-update@users.noreply.github.com"],
    ]
    for cmd in setup_cmds:
        subprocess.run(cmd, cwd=str(BASE_DIR), text=True, capture_output=True, timeout=30)

    cmds = [
        ["git", "add", "index.html", "assets/market_data.json"],
        ["git", "commit", "-m", f"chore: auto-update dashboard data {datetime.now().strftime('%Y-%m-%d %H:%M')}"],
        ["git", "push", remote_url, "main"],
    ]

    for cmd in cmds:
        result = subprocess.run(cmd, cwd=str(BASE_DIR), text=True, capture_output=True, timeout=60)
        combined_output = result.stdout + result.stderr
        if result.stdout.strip():
            print(f"[Git] {result.stdout.strip()}")
        if result.stderr.strip():
            print(f"[Git] {result.stderr.strip()}", file=sys.stderr)
        if result.returncode != 0 and "nothing to commit" not in combined_output:
            raise RuntimeError(f"Git 操作失败：{' '.join(cmd[:2])}")
    print("[Git] 推送完成")


def main():
    print("=" * 60)
    print("中证红利定投策略看板：数据更新")
    print("=" * 60)
    run_update()
    push_to_github()
    data = load_market_data()
    summary = compose_summary(data)
    print("=" * 60)
    print(summary)
    print("=" * 60)
    print("[DONE] 固定看板已更新")
    print("=" * 60)


if __name__ == "__main__":
    main()
