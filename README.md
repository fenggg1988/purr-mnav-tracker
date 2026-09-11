# PURR mNAV 动态监测系统 🐱

监测 **Hyperliquid Strategies Inc.（NASDAQ: PURR）** 的 mNAV（市值 / 净资产值）等核心指标，每日自动更新，图表化呈现。

## 在线看板（GitHub Pages）

`https://fenggg1988.github.io/purr-mnav-tracker/`

每次数据更新后自动重新部署（仓库为 Public + Pages Actions 部署源）。

## 本地查看

`dashboard/index.html` 数据已内嵌，直接浏览器打开即可。

## 核心指标

| 指标 | 口径 |
|---|---|
| **mNAV（毛）** | 市值 ÷ (HYPE 持仓市值 + 现金) |
| **mNAV（调整后）** | 市值 ÷ (毛 NAV − 递延所得税估算) |
| 溢价/折价率 | (mNAV − 1) × 100%，>1 溢价、<1 折价 |
| 每股 HYPE | HYPE 持仓 ÷ 流通股本 |
| 每股 NAV | NAV ÷ 流通股本 |

## 数据源

- **HYPE 价格**：Hyperliquid 官方 API（24/7）
- **PURR 股价**：stockanalysis.com（主）→ Yahoo Finance（备）
- **基本面**：`config.json` 手动维护（HYPE 持仓、现金、股本、递延税），随季报更新

## 运行

```bash
python fetch_data.py   # 拉数据 -> data/history.json -> 生成 dashboard/index.html
```

GitHub Actions 每**交易日北京时间 09:00** 自动运行：拉数据 → 提交 → 部署 Pages（`.github/workflows/update.yml`）。

## 更新基本面

季度财报公布后编辑 `config.json` 中 `fundamentals` 各项（持仓数量、现金、股本等）并提交即可，下次运行自动生效。

> 免责声明：自动生成的数据仅供参考，不构成投资建议。
