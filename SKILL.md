---
name: binance-alpha-hunter
description: 面向 Binance Alpha 场景的 OpenClaw skill。用于发现 Binance Alpha 候选标的、查询单个标的关键信息、生成风险摘要、生成 conservative 或 balanced 或 aggressive 交易计划，以及在用户明确确认后执行 paper trade 占位流程。用户提到 Binance Alpha、Alpha 候选、Alpha 风险、交易计划、观察列表、watchlist、paper trade、现货或合约预执行时使用。
---

# Binance Alpha Hunter

## 概览

这个 skill 先做只读 MVP，再为交易执行预留接口。默认优先使用 Binance Alpha 公共接口，不依赖独立前端页面，也不默认直接下真实订单。

## 何时触发

- 用户要找 Binance Alpha 候选标的
- 用户要看某个 Alpha 币的风险、流动性、波动性、是否适合新手
- 用户要按 `conservative`、`balanced`、`aggressive` 生成交易计划
- 用户要维护 Alpha watchlist
- 用户明确提出要先做 paper trade，或确认后再进入 execute_trade 占位流程

## 支持的用户意图

### 1. discover_alpha

- 找出当前 Binance Alpha 候选标的
- 输出 `symbol`、`price`、`24h_change`、`volume_24h`、`tags`
- 适合回答：
  - “帮我找 Alpha 候选”
  - “最近 Binance Alpha 有什么值得看”
  - “按成交量列 10 个 Alpha 候选”

调用：

```bash
python ~/.openclaw/skills/binance-alpha-hunter/tools/alpha_discover.py --limit 10 --sort volume
```

### 2. get_risk_report

- 对指定 `symbol` 输出风险摘要
- 必须至少包含：
  - `volatility_risk`
  - `liquidity_risk`
  - `beginner_friendly`
  - `suggested_mode`
- 同时补充关键信息：
  - `price`
  - `24h_change`
  - `volume_24h`
  - `liquidity`
  - `chain`
  - `contract_address`
  - `tags`

调用：

```bash
python ~/.openclaw/skills/binance-alpha-hunter/tools/alpha_risk.py UPUSDT
```

### 3. make_trade_plan

- 按风格生成交易计划：
  - `conservative`
  - `balanced`
  - `aggressive`
- 输出至少包含：
  - `entry`
  - `stop_loss`
  - `take_profit`
  - `position_size`
  - `invalidation`

调用：

```bash
python ~/.openclaw/skills/binance-alpha-hunter/tools/alpha_plan.py plan UPUSDT --style balanced
```

### 4. watchlist 管理

- `add`
- `remove`
- `list`

调用：

```bash
python ~/.openclaw/skills/binance-alpha-hunter/tools/alpha_watchlist.py add UPUSDT --note "观察量价结构"
python ~/.openclaw/skills/binance-alpha-hunter/tools/alpha_watchlist.py remove UPUSDT
python ~/.openclaw/skills/binance-alpha-hunter/tools/alpha_watchlist.py list
```

### 5. execute_trade

- 当前只做占位接口
- 默认模式是 `paper`
- 真实 `Binance Spot / Futures` 下单暂不启用
- 只有在用户明确确认“执行”时，才允许调用这个流程

调用：

```bash
python ~/.openclaw/skills/binance-alpha-hunter/tools/alpha_plan.py execute UPUSDT --side buy --style balanced --amount-usd 100 --confirm
```

## 工作流程

1. 先用 `alpha_discover.py` 找候选
2. 再用 `alpha_risk.py` 看单标的风险
3. 需要计划时用 `alpha_plan.py plan`
4. 想持续跟踪时写入 `watchlist.json`
5. 比赛演示优先用 `alpha_discover.py --competition-mode`
6. 想体现持续跟踪时用 `alpha_watchlist.py compare`
7. 用户明确确认后，才允许走 `alpha_plan.py execute`

## 输出格式

优先输出结构化 JSON，便于 OpenClaw 后续拼接自然语言回复。

### discover_alpha 输出

- `items`
  - 每项包含：
    - `symbol`
    - `price`
    - `24h_change`
    - `volume_24h`
    - `tags`
- `count`
- `sort`
- `updated_at`

### get_risk_report 输出

- `symbol`
- `key_info`
- `volatility_risk`
- `liquidity_risk`
- `beginner_friendly`
- `suggested_mode`
- `risk_summary`
- `notes`

### make_trade_plan 输出

- `symbol`
- `style`
- `entry`
- `stop_loss`
- `take_profit`
- `position_size`
- `invalidation`
- `execution_mode`

## 风险提示

- 默认不直接交易
- 没有用户明确确认，不要调用 `execute_trade`
- `execute_trade` 在当前 MVP 默认只做 `paper trade`
- 即便用户要求真实下单，也应先说明当前版本仅预留接口，真实 Spot 或 Futures 需要后续接入并再次确认
- 如果输出里出现 `data_source=cache_fallback` 或 `stale=true`，应明确告知当前结果包含缓存回退

## 本地文件

- Watchlist：
  - `~/.openclaw/skills/binance-alpha-hunter/data/watchlist.json`
- 示例提示词：
  - `~/.openclaw/skills/binance-alpha-hunter/examples/demo_prompts.md`

## 实际使用时的表达方式

- 先给候选列表，再给风险摘要，再给交易计划
- 不要把风险报告伪装成确定性建议
- 不要在没有确认的情况下把 `plan` 自动升级成 `execute`
