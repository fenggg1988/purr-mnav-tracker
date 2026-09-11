#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PURR (Hyperliquid Strategies Inc.) mNAV 动态监测 - 数据采集脚本
数据源:
  - HYPE 价格: Hyperliquid 官方 API (POST /info, type=allMids)
  - PURR 股价: stockanalysis.com API (主) / Yahoo Finance chart API (备)
  - 基本面: config.json (手动维护, 随季报更新)
输出:
  - data/history.json  每日历史序列
  - data/latest.json   最新快照
  - dashboard/index.html 自包含看板 (内嵌数据)
"""
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone, timedelta

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE, "data")
HISTORY_FILE = os.path.join(DATA_DIR, "history.json")
LATEST_FILE = os.path.join(DATA_DIR, "latest.json")
DASHBOARD_FILE = os.path.join(BASE, "dashboard", "index.html")
CONFIG_FILE = os.path.join(BASE, "config.json")

CST = timezone(timedelta(hours=8))
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"}


def http_json(url, data=None, headers=None, timeout=25):
    req = urllib.request.Request(url, data=data, headers=headers or UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def fetch_hype_price():
    """Hyperliquid 官方 API, 返回 HYPE 中间价"""
    payload = json.dumps({"type": "allMids"}).encode()
    d = http_json("https://api.hyperliquid.xyz/info", data=payload,
                  headers={"Content-Type": "application/json", **UA})
    return float(d["HYPE"])


def fetch_purr_stockanalysis():
    """stockanalysis.com 日线, 返回 (最新收盘价, 历史序列 [(date, close)], 来源名)"""
    d = http_json("https://stockanalysis.com/api/symbol/s/purr/history?range=5Y&period=Daily")
    rows = [(x["t"], float(x["c"])) for x in d["data"]]
    rows.sort()
    return rows[-1][1], rows, "stockanalysis"


def fetch_purr_yahoo():
    """Yahoo Finance 备用源"""
    d = http_json("https://query2.finance.yahoo.com/v8/finance/chart/PURR?interval=1d&range=5y")
    res = d["chart"]["result"][0]
    ts = res["timestamp"]
    closes = res["indicators"]["quote"][0]["close"]
    rows = []
    for t, c in zip(ts, closes):
        if c is None:
            continue
        rows.append((datetime.fromtimestamp(t, tz=timezone.utc).strftime("%Y-%m-%d"), round(float(c), 4)))
    rows.sort()
    return rows[-1][1], rows, "yahoo"


def fetch_purr_price():
    errors = []
    for fn in (fetch_purr_stockanalysis, fetch_purr_yahoo):
        try:
            return fn()
        except Exception as e:
            errors.append(f"{fn.__name__}: {e}")
    raise RuntimeError("PURR 股价所有数据源均失败: " + " | ".join(errors))


def compute_metrics(purr_price, hype_price, fund):
    shares = fund["shares_outstanding"]["value"]
    hype_n = fund["hype_holdings"]["value"]
    cash = fund["cash"]["value"]
    dtl = fund["deferred_tax_liability"]["value"]

    market_cap = purr_price * shares
    gross_nav = hype_n * hype_price + cash          # 毛 NAV = HYPE 市值 + 现金
    adj_nav = gross_nav - dtl                        # 调整后 NAV = 扣递延税
    mnav_gross = market_cap / gross_nav if gross_nav else None
    mnav_adj = market_cap / adj_nav if adj_nav else None
    hype_per_share = hype_n / shares
    nav_per_share_gross = gross_nav / shares
    nav_per_share_adj = adj_nav / shares
    premium_gross = (mnav_gross - 1) * 100 if mnav_gross else None
    premium_adj = (mnav_adj - 1) * 100 if mnav_adj else None

    return {
        "market_cap": round(market_cap, 2),
        "gross_nav": round(gross_nav, 2),
        "adj_nav": round(adj_nav, 2),
        "mnav_gross": round(mnav_gross, 4) if mnav_gross else None,
        "mnav_adj": round(mnav_adj, 4) if mnav_adj else None,
        "premium_gross": round(premium_gross, 2) if premium_gross is not None else None,
        "premium_adj": round(premium_adj, 2) if premium_adj is not None else None,
        "hype_per_share": round(hype_per_share, 5),
        "nav_per_share_gross": round(nav_per_share_gross, 3),
        "nav_per_share_adj": round(nav_per_share_adj, 3),
    }


def main():
    with open(CONFIG_FILE, encoding="utf-8") as f:
        config = json.load(f)
    fund = config["fundamentals"]

    hype_price = fetch_hype_price()
    purr_price, purr_hist, purr_source = fetch_purr_price()
    metrics = compute_metrics(purr_price, hype_price, fund)

    today = datetime.now(CST).strftime("%Y-%m-%d")
    ts = datetime.now(CST).strftime("%Y-%m-%dT%H:%M:%S+08:00")

    # 历史: PURR 全部日线 (供股价/NAV走势), 加上每日计算的 mNAV 快照
    history_path = os.path.join(DATA_DIR, "history.json")
    history = {"purr_daily": [], "snapshots": []}
    if os.path.exists(history_path):
        with open(history_path, encoding="utf-8") as f:
            history = json.load(f)

    history["purr_daily"] = purr_hist  # 全量刷新

    snapshots = {s["date"]: s for s in history.get("snapshots", [])}
    snapshots[today] = {
        "date": today, "timestamp": ts,
        "purr_price": purr_price, "hype_price": round(hype_price, 4),
        "purr_source": purr_source, **metrics,
    }
    history["snapshots"] = sorted(snapshots.values(), key=lambda s: s["date"])

    with open(history_path, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=1)

    latest = {
        "updated_at": ts, "date": today,
        "purr_price": purr_price, "hype_price": round(hype_price, 4),
        "purr_source": purr_source, "fundamentals": fund, **metrics,
    }
    with open(LATEST_FILE, "w", encoding="utf-8") as f:
        json.dump(latest, f, ensure_ascii=False, indent=1)

    build_dashboard(history, latest)

    print(f"[OK] {ts}")
    print(f"  PURR 股价   : ${purr_price}  (源: {purr_source})")
    print(f"  HYPE 价格   : ${hype_price}")
    print(f"  市值        : ${metrics['market_cap']:,.0f}")
    print(f"  毛 NAV      : ${metrics['gross_nav']:,.0f}")
    print(f"  调整后 NAV  : ${metrics['adj_nav']:,.0f}")
    print(f"  mNAV (毛)   : {metrics['mnav_gross']}x")
    print(f"  mNAV (调整) : {metrics['mnav_adj']}x")
    print(f"  溢价/折价   : {metrics['premium_gross']}% (毛) / {metrics['premium_adj']}% (调整)")


def build_dashboard(history, latest):
    """生成自包含 HTML 看板 (数据内嵌)"""
    with open(os.path.join(BASE, "dashboard", "template.html"), encoding="utf-8") as f:
        tpl = f.read()
    payload = json.dumps({"history": history, "latest": latest}, ensure_ascii=False)
    # 安全内嵌: 防止 </script> 提前闭合
    payload = payload.replace("</", "<\\/")
    html = tpl.replace("__DATA__", payload)
    with open(DASHBOARD_FILE, "w", encoding="utf-8") as f:
        f.write(html)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[FAIL] {e}", file=sys.stderr)
        sys.exit(1)
