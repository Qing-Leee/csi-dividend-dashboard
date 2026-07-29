# 中证红利定投策略看板自动化说明

## 目标

这个目录现在按"稳定静态站点 + 自动输出小结"的方式组织。

自动化任务不应再创建新的报告或 artifact，而应只做三件事：

1. 更新固定看板数据
2. 覆盖固定看板入口
3. 输出数据小结和看板链接（直接返回，无需飞书通知）

## 稳定入口

固定入口文件：

```text
index.html
```

数据文件：

```text
assets/market_data.json
```

更新脚本：

```text
scripts/update_data.py
```

总入口脚本：

```text
scripts/run_update_and_notify.py
```

## 推荐定时任务

每日两个任务：

```text
08:00 盘前版
14:30 盘中版
```

每次运行：

```bash
python3 scripts/run_update_and_notify.py
```

如果在定时任务的新会话中运行，先拉取仓库：

```bash
git clone https://github.com/Qing-Leee/csi-dividend-dashboard.git /tmp/csi-dividend-dashboard
cd /tmp/csi-dividend-dashboard
python3 scripts/run_update_and_notify.py
```

## 环境变量

稳定看板链接：

```bash
export DASHBOARD_PUBLIC_URL="https://qing-leee.github.io/csi-dividend-dashboard/"
```

GitHub 推送 Token（可选，不配置则跳过推送）：

```bash
export GITHUB_TOKEN="ghp_xxx"
```

## 输出小结内容

运行完成后，脚本会在终端输出以下小结：

- 更新时间
- 外部数据截至日期
- 累计投入
- 持有市值
- 累计收益率
- 浮盈/亏
- PE2
- D/P2
- RSI24
- 股债利差
- 综合建议
- 看板链接（可直接点击访问）

## 静态站点说明

"静态站点"就是一个固定网址，用来放 `index.html`。

目前本目录已部署到 GitHub Pages：

```text
https://qing-leee.github.io/csi-dividend-dashboard/
```

自动化任务运行后，脚本会自动将更新的 index.html 和 market_data.json 推送到 GitHub，
GitHub Pages 会在约 1-2 分钟后刷新。

## 重要约束

自动化任务提示词中必须明确：

```text
不要创建新的交付物。
不要生成新的 artifact。
只覆盖更新现有固定看板文件，并返回数据小结与看板链接。
```
