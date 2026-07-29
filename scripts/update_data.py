#!/usr/bin/env python3
"""
中证红利定投策略看板 - 数据更新脚本
在每日定时任务（08:00盘前 / 14:30盘中）执行，完成以下工作：
1. 抓取公开市场数据：中证官网指数估值Excel（PE2/DivYield2）、东方财富历史行情（收盘价）、十年期国债收益率
2. 同步内部数据源：飞书多维表格定投复盘记录（累计投入、持有市值、收益率等）
3. 计算RSI24（Wilder/RMA方法）、股债利差、策略建议
4. 输出 market_data.json 供前端看板加载
"""

import json
import os
import sys
import subprocess
import urllib.request
import urllib.error
from datetime import datetime, timedelta
from pathlib import Path

# ===== Paths =====
BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_PATH = str(BASE_DIR / "assets" / "market_data.json")
BOND_CACHE = "/tmp/bond_yield_investing.json"
FEISHU_CACHE = "/tmp/feishu_records.json"
DISPLAY_DATE = "2026-07-28"  # 外部公开数据统一展示至该日期

# ===== Constants =====
CSI_CODE = "000922"  # 中证红利
CSI_VALUATION_URL = f"https://oss-ch.csindex.com.cn/static/html/csindex/public/uploads/file/autofile/indicator/{CSI_CODE}indicator.xls"
EASTMONEY_KLINE_URL = "https://push2his.eastmoney.com/api/qt/stock/kline/get"

# ===== Helpers =====

def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def period_label():
    h = datetime.now().hour
    return "盘前" if h < 12 else "盘中"

def is_trading_day():
    # 简单判断：周一到周五
    return datetime.now().weekday() < 5

def http_get(url, timeout=15):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()

def json_get(url, timeout=15):
    return json.loads(http_get(url, timeout))

# ===== Data Source 1: East Money - Index Historical K-line =====

def fetch_eastmoney_kline(code="000922", days=60):
    """从东方财富获取指数日K线历史行情，用于计算RSI24和指数点位走势"""
    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=days + 60)).strftime("%Y%m%d")
    url = (
        f"{EASTMONEY_KLINE_URL}?secid=1.{code}"
        f"&fields1=f1,f2,f3,f4,f5,f6"
        f"&fields2=f51,f52,f53,f54,f55,f56,f57,f58"
        f"&klt=101&fqt=0"
        f"&beg={start_date}&end={end_date}"
        f"&lmt={days + 60}"
    )
    try:
        data = json_get(url)
        klines = data.get("data", {}).get("klines", [])
        result = []
        for k in klines:
            parts = k.split(",")
            if len(parts) >= 6:
                result.append({
                    "date": parts[0],
                    "open": float(parts[1]),
                    "close": float(parts[2]),
                    "high": float(parts[3]),
                    "low": float(parts[4]),
                    "volume": int(float(parts[5])),
                    "amount": float(parts[6]) if len(parts) > 6 else 0,
                    "change_pct": float(parts[8]) if len(parts) > 8 else 0,
                    "change_amt": float(parts[7]) if len(parts) > 7 else 0,
                })
        print(f"[EastMoney] 获取 {len(result)} 条K线数据")
        return result
    except Exception as e:
        print(f"[EastMoney] ERROR: {e}")
        return []

# ===== Data Source 2: CSI Index Valuation Excel =====

def fetch_csi_valuation(code="000922"):
    """
    从中证指数官网获取指数估值Excel，提取PE2和DivYield2
    Excel格式为旧版.xls，使用xlrd解析
    """
    try:
        raw = http_get(CSI_VALUATION_URL, timeout=20)
        # 尝试用xlrd解析
        try:
            import xlrd
        except ImportError:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "xlrd", "--break-system-packages", "-q"])
            import xlrd
        
        import io
        wb = xlrd.open_workbook(file_contents=raw)
        ws = wb.sheet_by_index(0)
        
        # 中证估值Excel通常有表头行，数据从第2或第3行开始
        # 列：日期, 市盈率1, 市盈率2, 市净率1, 市净率2, 股息率1, 股息率2, ...
        headers = [ws.cell_value(0, c) for c in range(ws.ncols)]
        
        pe2_col = None
        div2_col = None
        date_col = 0
        
        for i, h in enumerate(headers):
            h_str = str(h).strip()
            if "市盈率2" in h_str or "PE2" in h_str.upper() or ("盈率" in h_str and "2" in h_str):
                pe2_col = i
            if "股息率2" in h_str or "DP2" in h_str.upper() or ("股息" in h_str and "2" in h_str):
                div2_col = i
        
        # 如果找不到列名，用默认位置（通常PE2在第2列，DivYield2在第6列）
        if pe2_col is None:
            pe2_col = 2
        if div2_col is None:
            div2_col = 6
        
        def normalize_date(cell_value):
            raw_date = str(cell_value).strip()
            try:
                if isinstance(cell_value, float):
                    dt = xlrd.xldate_as_tuple(cell_value, wb.datemode)
                    return f"{dt[0]:04d}-{dt[1]:02d}-{dt[2]:02d}"
            except Exception:
                pass
            if len(raw_date) == 8 and raw_date.isdigit():
                return f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:8]}"
            return raw_date

        # 中证估值文件通常按日期倒序排列，不能假设最后一行是最新。
        # 逐行解析后按日期排序，取日期最大的一行作为最新值。
        parsed_rows = []
        for r in range(1, ws.nrows):
            try:
                d = normalize_date(ws.cell_value(r, date_col))
                pe = float(ws.cell_value(r, pe2_col))
                dv = float(ws.cell_value(r, div2_col))
                parsed_rows.append({"date": d, "pe2": pe, "div_yield2": dv})
            except Exception:
                continue

        if not parsed_rows:
            raise ValueError("中证估值Excel未解析到有效数据行")

        parsed_rows.sort(key=lambda row: row["date"])
        latest = parsed_rows[-1]
        pe2_val = latest["pe2"]
        div_yield2_val = latest["div_yield2"]
        date_val = latest["date"]
        history = parsed_rows[-30:]
        
        result = {
            "pe2": pe2_val,
            "div_yield2": div_yield2_val,
            "date": date_val,
            "history": history
        }
        print(f"[CSI] PE2={pe2_val}, DivYield2={div_yield2_val}%, date={date_val}, history={len(history)} rows")
        return result
    except Exception as e:
        print(f"[CSI] ERROR: {e}")
        return None

# ===== Data Source 3: Bond Yield (from cached WebFetch) =====

def fetch_bond_yield():
    """读取WebFetch缓存的十年期国债收益率"""
    try:
        with open(BOND_CACHE, 'r') as f:
            data = json.load(f)
        y10 = float(data.get("y10", 1.725))
        date = data.get("date", DISPLAY_DATE)
        print(f"[Bond] 十年期国债收益率={y10}%, date={date}")
        return {"y10": y10, "date": date}
    except Exception as e:
        print(f"[Bond] WARN: 读取缓存失败({e})，使用默认值1.725")
        return {"y10": 1.725, "date": DISPLAY_DATE}

# ===== Data Source 4: Bond Yield History (中债登) =====

def fetch_bond_yield_history():
    """获取中债登十年期国债收益率历史数据"""
    # 这里使用预设的历史数据作为基础，实际更新时只追加最新值
    # 完整的历史数据已包含在market_data.json中
    return None  # 使用现有JSON中的历史数据

# ===== Data Source 5: Internal Feishu Records =====

def fetch_feishu_records():
    """
    同步飞书多维表格中的定投复盘记录
    方式1：从 /tmp/feishu_records.json 读取（由定时任务中的lark-cli步骤写入）
    方式2：直接调用 lark-cli 命令获取
    方式3：回退到现有 market_data.json 中的记录
    """
    # 方式1：读取缓存文件
    if os.path.exists(FEISHU_CACHE):
        try:
            with open(FEISHU_CACHE, 'r') as f:
                records = json.load(f)
            if isinstance(records, list) and len(records) > 0:
                print(f"[Feishu] 从缓存读取 {len(records)} 条定投记录")
                return records
        except Exception as e:
            print(f"[Feishu] WARN: 缓存读取失败({e})，尝试lark-cli")
    
    # 方式2：尝试调用 lark-cli 获取飞书Base数据
    try:
        result = subprocess.run(
            ["lark-cli", "base", "record", "search",
             "--app-token", os.environ.get("FEISHU_APP_TOKEN", ""),
             "--table-id", os.environ.get("FEISHU_TABLE_ID", ""),
             "--as", "user",
             "--json"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0 and result.stdout.strip():
            cli_data = json.loads(result.stdout)
            records = parse_feishu_cli_records(cli_data)
            if records:
                print(f"[Feishu] 通过lark-cli获取 {len(records)} 条定投记录")
                # 缓存到文件供后续使用
                with open(FEISHU_CACHE, 'w') as f:
                    json.dump(records, f, ensure_ascii=False, indent=2)
                return records
    except Exception as e:
        print(f"[Feishu] WARN: lark-cli调用失败({e})")
    
    # 方式3：回退到现有market_data.json中的记录
    if os.path.exists(OUTPUT_PATH):
        try:
            with open(OUTPUT_PATH, 'r') as f:
                existing = json.load(f)
            records = existing.get("feishu_records", [])
            print(f"[Feishu] 回退到现有记录 {len(records)} 条（未能获取最新飞书数据）")
            return records
        except:
            pass
    
    print("[Feishu] ERROR: 无法获取飞书记录，返回空列表")
    return []

def parse_feishu_cli_records(cli_data):
    """解析lark-cli返回的飞书Base记录，转换为看板所需格式"""
    records = []
    items = cli_data.get("data", {}).get("items", cli_data.get("items", []))
    if not isinstance(items, list):
        items = [items] if items else []
    
    for item in items:
        fields = item.get("fields", {})
        try:
            record = {
                "date": str(fields.get("日期", fields.get("记录时间", "")))[:10],
                "action": str(fields.get("操作", fields.get("定投动作", "买入"))),
                "invest": float(fields.get("本期投入", 0) or 0),
                "shares": float(fields.get("本期份额", 0) or 0),
                "nav": float(fields.get("净值", 0) or 0),
                "cum_invest": float(fields.get("累计投入", 0) or 0),
                "cum_shares": float(fields.get("累计份额", 0) or 0),
                "mkt_value": float(fields.get("持有市值", fields.get("持有总市值", 0)) or 0),
                "cum_return_pct": float(fields.get("累计收益率", 0) or 0),
                "pnl": float(fields.get("浮盈", fields.get("浮盈/亏", 0)) or 0),
                "avg_cost": float(fields.get("均成本", fields.get("平均持仓成本", 0)) or 0),
            }
            records.append(record)
        except Exception as e:
            print(f"[Feishu] WARN: 解析记录失败: {e}")
            continue
    
    # 按日期排序
    records.sort(key=lambda r: r["date"])
    return records

# ===== RSI Calculation (Wilder/RMA) =====

def calculate_rsi(closes, period=24):
    """
    使用 Wilder 的 RMA 方法计算 RSI
    RSI = 100 - (100 / (1 + RS))
    RS = avg_gain / avg_loss
    首次avg使用SMA，后续使用RMA（指数平滑）
    """
    if len(closes) < period + 1:
        return 50.0
    
    gains = []
    losses = []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i-1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    
    # 初始平均使用SMA
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    
    # 后续使用RMA（Wilder平滑）
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return round(rsi, 2)

def calculate_rsi_history(closes, dates, period=24):
    """计算RSI历史序列"""
    result = []
    if len(closes) < period + 1:
        return result
    
    for i in range(period, len(closes)):
        rsi = calculate_rsi(closes[:i+1], period)
        result.append({"date": dates[i], "close": closes[i], "rsi24": rsi})
    
    return result

# ===== Strategy Advice Generation =====

def generate_strategy_advice(pe2, div_yield2, rsi24, spread):
    """根据PE、股息率、RSI、股债利差四因子生成策略建议"""
    
    # PE评分: <7.5:+1, <=10.5:0, >10.5:-1
    if pe2 < 7.5:
        pe_score = 1
        pe_advice = {"action": "强力买入", "detail": f"PE {pe2} 极度低估，建议加倍定投", "level": "strong_buy"}
    elif pe2 <= 10.5:
        pe_score = 0
        pe_advice = {"action": "持有观望", "detail": f"PE {pe2} 处于合理区间，维持基础定投或持有", "level": "hold"}
    else:
        pe_score = -1
        pe_advice = {"action": "谨慎", "detail": f"PE {pe2} 偏高，建议减少定投或暂停", "level": "caution"}
    
    # 股息率评分: >5.74:+1, >=3.42:0, <3.42:-1
    if div_yield2 > 5.74:
        div_score = 1
        div_advice = {"action": "买入", "detail": f"股息率 {div_yield2}% 处于高位，适合买入", "level": "buy"}
    elif div_yield2 >= 3.42:
        div_score = 0
        div_advice = {"action": "正常区间", "detail": f"股息率 {div_yield2}% 处于正常区间，可继续持有", "level": "hold"}
    else:
        div_score = -1
        div_advice = {"action": "谨慎", "detail": f"股息率 {div_yield2}% 偏低，估值偏高", "level": "caution"}
    
    # RSI评分: <30:+1, <=70:0, >70:-1
    if rsi24 < 30:
        rsi_score = 1
        rsi_advice = {"action": "超卖买入", "detail": f"RSI24={rsi24} 超卖区间，适合逢低买入", "level": "buy"}
    elif rsi24 <= 70:
        rsi_score = 0
        rsi_advice = {"action": "正常区间", "detail": f"RSI24={rsi24} 处于正常区间，无明显信号", "level": "hold"}
    else:
        rsi_score = -1
        rsi_advice = {"action": "超买谨慎", "detail": f"RSI24={rsi24} 超买区间，注意回调风险", "level": "caution"}
    
    # 股债利差评分: >3.5:+1, >=2.5:0, <2.5:-1
    if spread > 3.5:
        spread_score = 1
        spread_advice = {"action": "强力买入", "detail": f"股债利差 {spread}% 极高，股票极具配置价值", "level": "strong_buy"}
    elif spread >= 2.5:
        spread_score = 0
        spread_advice = {"action": "买入", "detail": f"股债利差 {spread}% 较高，适合分批买入", "level": "buy"}
    else:
        spread_score = -1
        spread_advice = {"action": "持有", "detail": f"股债利差 {spread}% 偏低，吸引力下降", "level": "hold"}
    
    # 综合评分
    total_score = pe_score + div_score + rsi_score + spread_score
    
    if total_score >= 3:
        composite = {"action": "强力买入", "detail": f"综合评分 {total_score}/4，多因子共振，极具配置价值", "level": "strong_buy"}
    elif total_score >= 1:
        composite = {"action": "买入", "detail": f"综合评分 {total_score}/4，适合分批布局", "level": "buy"}
    elif total_score == 0:
        composite = {"action": "持有", "detail": f"综合评分 {total_score}/4，维持基础定投", "level": "hold"}
    else:
        composite = {"action": "谨慎", "detail": f"综合评分 {total_score}/4，偏谨慎，建议减少定投", "level": "pause"}
    
    return {
        "pe_advice": pe_advice,
        "div_advice": div_advice,
        "spread_advice": spread_advice,
        "rsi_advice": rsi_advice,
        "composite_advice": composite,
        "composite_score": total_score,
        "spread": round(spread, 2)
    }

# ===== Stock-Bond Spread History =====

def build_spread_history(valuation_history, bond_history):
    """构建股债利差历史"""
    bond_by_date = {}
    for b in bond_history:
        bond_by_date[b["date"]] = b["y10"]
    
    spread_history = []
    for v in valuation_history:
        d = v["date"]
        dv = v["div_yield2"]
        y10 = bond_by_date.get(d)
        if y10 is None:
            continue
        spread = round(dv - y10, 2)
        spread_history.append({
            "date": d,
            "div_yield2": dv,
            "y10": y10,
            "spread": spread,
            "bond_source": "中央国债登记结算有限责任公司"
        })
    
    return spread_history

# ===== Inline data into HTML for self-contained sharing =====

HTML_PATH = str(BASE_DIR / "index.html")

def inline_data_into_html(data):
    """
    将 market_data.json 数据内联到 HTML 文件中，生成自包含的可分享文件。
    
    HTML 已经是自包含的（echarts.min.js、charts.js、字体全部内联），
    此函数只需替换 window.__MARKET_DATA__ 中的旧数据。
    同时清理 ECharts 渲染后残留的 tooltip DOM 污染。
    """
    import re
    import base64
    import os
    
    try:
        with open(HTML_PATH, 'r', encoding='utf-8') as f:
            html = f.read()
        
        # 构建新的内联 script
        new_inline = '<script>window.__MARKET_DATA__ = ' + json.dumps(data, ensure_ascii=False, indent=2) + ';</script>'
        
        # 替换已有的内联数据（匹配 <script>window.__MARKET_DATA__ = {...};</script>）
        pattern = r'<script>window\.__MARKET_DATA__\s*=\s*[\s\S]*?;</script>'
        if re.search(pattern, html):
            html = re.sub(pattern, new_inline, html)
            print(f"[HTML] 替换已有内联数据")
        else:
            print(f"[HTML] WARN: 未找到 __MARKET_DATA__ 标签，跳过数据内联")
        
        # 清理 ECharts tooltip DOM 污染
        # 找到最后一个 </script> 标签
        last_script_end = html.rfind('</script>')
        if last_script_end != -1:
            after_scripts = html[last_script_end:]
            body_end = after_scripts.find('</body>')
            if body_end != -1:
                between = after_scripts[:body_end]
                if '<div' in between:
                    # 移除所有 div 标签（ECharts tooltip 残留）
                    clean = re.sub(r'<div[^>]*>.*?</div>', '', between, flags=re.DOTALL)
                    clean = re.sub(r'<div[^>]*/>', '', clean)
                    clean = clean.strip()
                    html = html[:last_script_end + len('</script>')]
                    if clean:
                        html += '\n' + clean
                    html += '\n</body>\n</html>\n'
                    print(f"[HTML] 清理了 tooltip DOM 污染")
        
        with open(HTML_PATH, 'w', encoding='utf-8') as f:
            f.write(html)
        
        print(f"[HTML] 自包含文件已更新: {HTML_PATH}")
    except Exception as e:
        print(f"[HTML] ERROR: 内联数据失败: {e}")
        import traceback
        traceback.print_exc()

# ===== Main =====

def main():
    print(f"{'='*60}")
    print(f"中证红利定投策略看板 - 数据更新")
    print(f"时间: {now_str()}")
    print(f"{'='*60}")
    
    # 读取现有数据（作为回退基础）
    existing_data = {}
    if os.path.exists(OUTPUT_PATH):
        try:
            with open(OUTPUT_PATH, 'r') as f:
                existing_data = json.load(f)
            print(f"[Existing] 读取现有 market_data.json 作为回退基础")
        except:
            pass
    
    # ===== Step 1: 东财历史K线 =====
    klines = fetch_eastmoney_kline(CSI_CODE, days=90)
    closes = [k["close"] for k in klines]
    dates = [k["date"] for k in klines]
    
    # 构建公开行情历史
    public_history_data = klines
    
    # 最新指数点位
    latest_index = {
        "name": "中证红利",
        "code": CSI_CODE,
        "date": klines[-1]["date"] if klines else DISPLAY_DATE,
        "latest": klines[-1]["close"] if klines else 5437.92,
        "change_pct": klines[-1].get("change_pct", 0) if klines else 0,
        "change_amt": klines[-1].get("change_amt", 0) if klines else 0,
        "volume": klines[-1].get("volume", 0) if klines else 0,
        "amount": klines[-1].get("amount", 0) if klines else 0,
        "high": klines[-1].get("high", 0) if klines else 0,
        "low": klines[-1].get("low", 0) if klines else 0,
        "open": klines[-1].get("open", 0) if klines else 0,
        "source": "东方财富历史行情",
        "source_url": "https://quote.eastmoney.com/"
    }
    
    # ===== Step 2: RSI24 计算 =====
    rsi_history = calculate_rsi_history(closes, dates, period=24) if len(closes) > 24 else []
    latest_rsi = rsi_history[-1]["rsi24"] if rsi_history else 50.0
    print(f"[RSI] RSI24={latest_rsi}, history={len(rsi_history)} rows")
    
    # 回退到现有数据
    if not rsi_history and existing_data:
        rsi_history = existing_data.get("technical_history", {}).get("csi_dividend", {}).get("data", [])
        latest_rsi = existing_data.get("technical", {}).get("rsi24", 50.0)
        print(f"[RSI] 回退到现有数据, RSI24={latest_rsi}")
    
    # ===== Step 3: 中证指数估值 =====
    csi_val = fetch_csi_valuation(CSI_CODE)
    if csi_val:
        pe2 = csi_val["pe2"]
        div_yield2 = csi_val["div_yield2"]
        val_date = csi_val["date"]
        val_history = csi_val["history"]
    else:
        # 回退到现有数据
        csi_div_existing = existing_data.get("index_valuation", {}).get("csi_dividend", {})
        pe2 = csi_div_existing.get("pe2", 10.66)
        div_yield2 = csi_div_existing.get("div_yield2", 4.47)
        val_date = csi_div_existing.get("date", DISPLAY_DATE)
        val_history = existing_data.get("index_valuation_history", {}).get("csi_dividend", {}).get("data", [])
        print(f"[CSI] 回退到现有数据, PE2={pe2}, DivYield2={div_yield2}")
    
    # ===== Step 4: 十年期国债收益率 =====
    bond = fetch_bond_yield()
    y10 = bond["y10"]
    bond_date = bond["date"]
    
    # 国债历史数据：优先使用现有JSON中的历史
    bond_history = existing_data.get("bond_yield_history", {}).get("china_10y", {}).get("data", [])
    # 如果有新的国债数据，追加/更新
    bond_dates_existing = {b["date"] for b in bond_history}
    if bond_date not in bond_dates_existing:
        bond_history.append({
            "date": bond_date,
            "y10": y10,
            "source": "Investing.com (英为财情)"
        })
    
    # ===== Step 5: 内部飞书数据同步 =====
    print(f"\n[Feishu] 开始同步飞书定投复盘记录...")
    feishu_records = fetch_feishu_records()
    print(f"[Feishu] 获取 {len(feishu_records)} 条定投记录")
    
    # ===== Step 6: 股债利差 =====
    spread = round(div_yield2 - y10, 2)
    
    # 构建利差历史
    spread_history = build_spread_history(val_history, bond_history)
    # 追加今日数据
    if not spread_history or spread_history[-1]["date"] != val_date:
        spread_history.append({
            "date": val_date,
            "div_yield2": div_yield2,
            "y10": y10,
            "spread": spread,
            "bond_source": "Investing.com (英为财情)"
        })
    
    # ===== Step 7: 策略建议 =====
    strategy = generate_strategy_advice(pe2, div_yield2, latest_rsi, spread)
    
    # ===== Step 8: 组装输出 =====
    output = {
        "meta": {
            "update_time": now_str(),
            "period_label": period_label(),
            "is_trading_day": is_trading_day(),
            "data_sources": {
                "internal": {
                    "feishu_records": "飞书多维表格·用户定投复盘",
                    "fields": [
                        "累计投入", "持有总市值", "平均持仓成本",
                        "累计收益率", "浮盈/亏", "定投动作", "份额", "净值"
                    ]
                },
                "public": {
                    "index_spot": {
                        "name": "东方财富",
                        "url": "https://quote.eastmoney.com/"
                    },
                    "index_valuation": {
                        "name": "中证指数有限公司",
                        "url": "https://www.csindex.com.cn/"
                    },
                    "bond_yield": {
                        "name": "Investing.com (英为财情)",
                        "url": "https://cn.investing.com/rates-bonds/china-10-year-bond-yield",
                        "fallback": "中央国债登记结算有限责任公司"
                    }
                }
            },
            "update_schedule": "每日 08:00(盘前) / 14:30(盘中) 自动更新",
            "next_update": "14:30 盘中版（收盘前策略信号）" if period_label() == "盘前" else "次日 08:00 盘前版",
            "market_date": val_date,
            "valuation_policy": "中证官网指数估值Excel，计算使用P/E2与D/P2",
            "display_policy": f"外部公开数据统一展示至{val_date}，避免盘中实时波动"
        },
        "index_spot": {
            "csi_dividend": latest_index
        },
        "public_history": {
            "csi_dividend": {
                "name": "中证红利",
                "code": CSI_CODE,
                "source": "东方财富历史行情",
                "source_url": "https://quote.eastmoney.com/",
                "policy": "仅用于页面中的指数点位走势；飞书复盘记录不混入外部市场字段",
                "data": public_history_data
            }
        },
        "index_valuation": {
            "csi_dividend": {
                "pe2": pe2,
                "div_yield2": div_yield2,
                "date": val_date,
                "source": "中证指数有限公司指数估值Excel",
                "source_url": CSI_VALUATION_URL,
                "policy": "计算用指标：市盈率2（计算用股本）P/E2、股息率2（计算用股本）D/P2"
            }
        },
        "index_valuation_history": {
            "csi_dividend": {
                "name": "中证红利",
                "code": CSI_CODE,
                "source": "中证指数有限公司指数估值Excel",
                "source_url": CSI_VALUATION_URL,
                "policy": "日变动计算使用市盈率2（计算用股本）P/E2、股息率2（计算用股本）D/P2",
                "data": val_history if val_history else [{"date": val_date, "pe2": pe2, "div_yield2": div_yield2}]
            }
        },
        "bond_yield": {
            "date": bond_date,
            "y10": y10,
            "source": "Investing.com (英为财情)",
            "source_url": "https://cn.investing.com/rates-bonds/china-10-year-bond-yield",
            "note": f"按用户要求展示至{DISPLAY_DATE}昨日收盘口径"
        },
        "bond_yield_history": {
            "china_10y": {
                "name": "中国10年期国债收益率",
                "source": f"中债登每日收益率曲线；{bond_date} 使用 Investing.com 昨日收盘值",
                "source_url": "https://yield.chinabond.com.cn/",
                "investing_source_url": "https://cn.investing.com/rates-bonds/china-10-year-bond-yield",
                "data": bond_history
            }
        },
        "technical": {
            "date": val_date,
            "rsi24": latest_rsi,
            "source": "东方财富历史行情收盘价计算",
            "method": "RSI24=Wilder/RMA，基于中证红利日收盘价"
        },
        "technical_history": {
            "csi_dividend": {
                "name": "中证红利",
                "code": CSI_CODE,
                "source": "东方财富历史行情收盘价计算",
                "source_url": "https://quote.eastmoney.com/",
                "method": "RSI24=Wilder/RMA，基于中证红利每日收盘价滚动计算",
                "data": rsi_history
            }
        },
        "stock_bond_spread_history": {
            "csi_dividend": {
                "name": "中证红利股债利差",
                "method": "股债利差 = 中证红利 D/P2 - 中国10年期国债收益率",
                "source": "中证官网指数估值Excel + 每日国债收益率",
                "data": spread_history
            }
        },
        "feishu_records": feishu_records,
        "strategy_advice": strategy
    }
    
    # ===== Step 9: 写入 JSON 文件 =====
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    # ===== Step 10: 将数据内联到 HTML，生成自包含文件 =====
    inline_data_into_html(output)
    
    print(f"\n{'='*60}")
    print(f"[DONE] 数据已写入 {OUTPUT_PATH}")
    print(f"  - PE2: {pe2}, DivYield2: {div_yield2}%")
    print(f"  - RSI24: {latest_rsi}")
    print(f"  - 十年期国债: {y10}%")
    print(f"  - 股债利差: {spread}%")
    print(f"  - 飞书记录: {len(feishu_records)} 条")
    print(f"  - 综合建议: {strategy['composite_advice']['action']}")
    print(f"  - HTML已内联数据（自包含可分享）")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
