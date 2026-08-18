# A Stock Monitor

一个面向 A 股盘中监控的最小可运行服务，默认关注：

- 上证指数 `000001`
- 证券保险 ETF `512070`
- 电网设备 ETF `159326`
- 港股创新药 ETF `513120`
- 机器人 ETF `562500`
- 中粮糖业 `600737`
- 海南橡胶 `601118`

当前版本优先使用 AKShare/东方财富数据源，提供实时快照、1 分钟分时、规则判断和 HTTP API。后续可继续接入 mootdx 作为通达信分钟行情备份源。

## 已实现规则

- 上证指数 4000 点向上/向下穿越
- ETF 相对上证指数的强弱偏离
- 5 分钟快速拉升/跳水
- 1 分钟成交量相对近 20 分钟中位数的放量异动
- 主板股票涨停后开板检测（默认按 10% 涨跌停规则，可在配置中修改）

## 安装

建议 Python 3.11+。

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
```

## 启动 HTTP 服务

```bash
uvicorn app.api:app --host 0.0.0.0 --port 8000
```

接口：

- `GET /health`
- `GET /quote/600737?asset_type=stock`
- `GET /quote/512070?asset_type=etf`
- `GET /monitor/check`
- `GET /monitor/watchlist`

## 命令行持续监控

```bash
python -m app.cli --interval 30
```

默认每 30 秒检查一次。它只在当前进程运行时持续监控；GitHub 仓库本身不会自动常驻运行。要实现全天自动推送，需要把本项目部署到持续在线的服务器/云函数，并接入消息通知渠道。

## 配置

修改 `config.yaml` 即可调整监控标的和阈值。

## 数据源说明

- ETF 实时行情：AKShare `fund_etf_spot_em`
- ETF 1 分钟行情：AKShare `fund_etf_hist_min_em`
- A 股实时行情：AKShare `stock_zh_a_spot_em`
- A 股 1 分钟行情：AKShare `stock_zh_a_hist_min_em`
- 上证指数实时行情：AKShare `stock_zh_index_spot_em`
- 上证指数 1 分钟行情：AKShare `index_zh_a_hist_min_em`

这些接口底层数据主要来自东方财富，可能存在网络失败、字段调整或延迟。监控结果用于辅助观察，不应视为交易指令。

## 测试

```bash
pytest -q
```

测试仅验证本地规则逻辑，不依赖外部行情网络。
