# 中证红利定投策略看板自动化说明

## 目标

这个目录现在按“稳定静态站点 + 飞书应用机器人通知”的方式组织。

自动化任务不应再创建新的报告或 artifact，而应只做三件事：

1. 更新固定看板数据
2. 覆盖固定看板入口
3. 用飞书应用机器人推送摘要通知

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
python3 /workspace/csi-dividend-dca-dashboard/scripts/run_update_and_notify.py
```

## 环境变量

飞书应用机器人通知目标：

```bash
export FEISHU_CHAT_ID="oc_xxx"
```

或发送给指定用户：

```bash
export FEISHU_USER_ID="ou_xxx"
```

稳定看板链接：

```bash
export DASHBOARD_PUBLIC_URL="https://qing-leee.github.io/csi-dividend-dashboard/"
```

如果没有配置 `FEISHU_CHAT_ID` 或 `FEISHU_USER_ID`，脚本只会更新页面并打印消息预览，不会发送飞书通知。

## 飞书消息内容

通知会包含：

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
- 固定看板链接

## 静态站点说明

“静态站点”就是一个固定网址，用来放 `index.html`。

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
只覆盖更新现有固定看板文件，并发送飞书通知。
```
