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
- 当 lark-cli 认证过期时，自动生成重新认证提醒，并嵌入认证流程指引。
"""

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
UPDATE_SCRIPT = BASE_DIR / "scripts" / "update_data.py"
DATA_PATH = BASE_DIR / "assets" / "market_data.json"
DEFAULT_PREVIEW_DIR = Path("/workspace/csi-dividend-dashboard-preview")

# 飞书 Base 配置（用于认证提示）
FEISHU_BASE_TOKEN = "Z8yYbFOcZaBaFMsmt6xcnaFpnlf"
FEISHU_TABLE_ID = "tblJQJWinJCenmID"


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
    """构建推送摘要，包含数据小结和认证提醒"""
    meta = data.get("meta") or {}
    valuation = (data.get("index_valuation") or {}).get("csi_dividend") or {}
    technical = data.get("technical") or {}
    strategy = data.get("strategy_advice") or {}
    composite = strategy.get("composite_advice") or {}
    record = latest_record(data)
    freshness = meta.get("data_freshness") or {}
    feishu_freshness = freshness.get("feishu") or {}
    auth_needed = feishu_freshness.get("auth_needed", False)

    dashboard_url = os.environ.get(
        "DASHBOARD_PUBLIC_URL",
        "https://qing-leee.github.io/csi-dividend-dashboard/",
    ).strip()
    preview_url = os.environ.get(
        "DASHBOARD_PREVIEW_URL",
        "computer:///workspace/csi-dividend-dashboard-preview/index.html",
    ).strip()
    period = meta.get("period_label", "更新")
    update_time = meta.get("update_time") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = [
        f"中证红利定投策略看板已更新（{period}版）",
        "",
        f"更新时间：{update_time}",
        f"外部数据截至：{meta.get('market_date', '--')}",
    ]

    # ===== 认证过期提醒（优先级最高）=====
    if auth_needed:
        last_date = feishu_freshness.get("last_record_date", "N/A")
        lines.extend([
            "",
            "=" * 50,
            "🔑 飞书认证已过期，内部数据无法更新！",
            "=" * 50,
            "",
            f"问题：lark-cli 认证已过期或未授权，飞书内部数据使用了旧缓存（最新记录：{last_date}）",
            "影响：看板中的累计投入、持有市值、收益率等内部数据未更新",
            "",
            "请按以下步骤重新认证：",
            "",
            "步骤1：打开 TRAE AI Agent 对话窗口",
            "步骤2：发送以下指令：",
            f'  lark-cli auth login --scope "bitable:bitable" --as user',
            "",
            "步骤3：认证窗口会弹出授权链接，点击打开并完成飞书扫码授权",
            "步骤4：授权成功后，重新触发看板数据更新：",
            f"  python3 scripts/run_update_and_notify.py",
            "",
            "认证成功后，飞书内部数据将在下次更新时自动同步最新记录。",
            "=" * 50,
        ])

    # ===== 普通数据未更新提醒 =====
    elif not feishu_freshness.get("is_fresh", True):
        last_date = feishu_freshness.get("last_record_date", "N/A")
        lines.extend([
            "",
            f"⚠ 内部数据未更新：飞书数据同步失败，当前使用旧数据（最新记录：{last_date}）",
        ])

    # ===== 数据小结 =====
    lines.extend([
        "",
        "📊 数据小结：",
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
    ])

    # ===== 内部数据状态标识 =====
    if auth_needed:
        lines.extend(["", "🔴 内部数据状态：认证过期·需重新认证"])
    elif not feishu_freshness.get("is_fresh", True):
        lines.extend(["", "🟡 内部数据状态：使用旧缓存·非认证问题"])
    else:
        lines.extend(["", "🟢 内部数据状态：已同步最新"])

    if preview_url:
        lines.extend(["", f"内置预览链接：[点击查看看板]({preview_url})"])
    elif dashboard_url:
        lines.extend(["", f"看板链接：[点击查看看板]({dashboard_url})"])
    else:
        lines.extend(["", "看板链接：待配置 DASHBOARD_PUBLIC_URL 或 DASHBOARD_PREVIEW_URL"])

    return "\n".join(lines)


def sync_preview_folder():
    """将最新看板同步到固定预览目录，便于返回 TRAE 内置预览链接。"""
    preview_dir = Path(os.environ.get("DASHBOARD_PREVIEW_DIR", str(DEFAULT_PREVIEW_DIR))).resolve()
    preview_dir.mkdir(parents=True, exist_ok=True)

    for file_name in ["index.html"]:
        src = BASE_DIR / file_name
        if src.exists():
            shutil.copy2(src, preview_dir / file_name)

    for dir_name in ["assets", "_shared"]:
        src_dir = BASE_DIR / dir_name
        dst_dir = preview_dir / dir_name
        if src_dir.exists():
            shutil.copytree(src_dir, dst_dir, dirs_exist_ok=True)

    print(f"[Preview] 内置预览文件已同步：{preview_dir / 'index.html'}")


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
    sync_preview_folder()
    push_to_github()
    data = load_market_data()
    summary = compose_summary(data)
    print("=" * 60)
    print(summary)
    print("=" * 60)

    # 检查是否需要认证提醒
    freshness = (data.get("meta") or {}).get("data_freshness") or {}
    feishu_freshness = freshness.get("feishu") or {}
    auth_needed = feishu_freshness.get("auth_needed", False)

    if auth_needed:
        print()
        print("🔑" * 25)
        print("🔑  飞书认证已过期！请重新认证后再次运行更新")
        print("🔑" * 25)
        print()
        print("重新认证命令：")
        print('  lark-cli auth login --scope "bitable:bitable" --as user')
        print()
        print("认证成功后重新运行：")
        print("  python3 scripts/run_update_and_notify.py")
        print()

    print("[DONE] 固定看板已更新")
    print("=" * 60)


if __name__ == "__main__":
    main()
