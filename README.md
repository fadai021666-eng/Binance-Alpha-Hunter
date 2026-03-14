# Binance Alpha Hunter

一个给 OpenClaw 用的 Binance Alpha MVP skill。

目标很简单：

1. 发现 Binance Alpha 候选标的
2. 查询单个标的的关键信息和风险摘要
3. 生成交易计划
4. 管理 watchlist
5. 在用户确认后执行 paper trade 占位流程

当前版本优先使用 Binance Alpha 公共接口，不做前端页面，不默认接真实交易。

## 目录结构

```text
binance-alpha-hunter/
  SKILL.md
  README.md
  agents/
    openai.yaml
  tools/
    alpha_discover.py
    alpha_risk.py
    alpha_plan.py
    alpha_watchlist.py
  lib/
    __init__.py
    binance_alpha.py
    rules.py
    types.py
  data/
    watchlist.json
  examples/
    demo_prompts.md
```

## 数据来源

默认优先使用这些公开接口：

- `https://www.binance.com/bapi/defi/v1/public/wallet-direct/buw/wallet/cex/alpha/all/token/list`
- `https://www.binance.com/bapi/defi/v1/public/alpha-trade/get-exchange-info`
- `https://www.binance.com/bapi/defi/v1/public/alpha-trade/klines`
- `https://www.binance.com/bapi/defi/v1/public/alpha-trade/book-ticker`
- `https://web3.binance.com/bapi/defi/v1/public/wallet-direct/buw/wallet/dex/market/token/meta/info`

## 运行方式

直接执行 Python 脚本即可，不需要单独启动服务。

### 1. 发现候选

```bash
python ~/.openclaw/skills/binance-alpha-hunter/tools/alpha_discover.py --limit 10 --sort volume
python ~/.openclaw/skills/binance-alpha-hunter/tools/alpha_discover.py --keyword UP --sort change
python ~/.openclaw/skills/binance-alpha-hunter/tools/alpha_discover.py --mode momentum --sort score --limit 8
python ~/.openclaw/skills/binance-alpha-hunter/tools/alpha_discover.py --mode safe --sort score --limit 8
python ~/.openclaw/skills/binance-alpha-hunter/tools/alpha_discover.py --mode early --sort new --limit 8
python ~/.openclaw/skills/binance-alpha-hunter/tools/alpha_discover.py --mode contrarian --sort score --limit 8
python ~/.openclaw/skills/binance-alpha-hunter/tools/alpha_discover.py --mode momentum --sort score --limit 5 --presentation
python ~/.openclaw/skills/binance-alpha-hunter/tools/alpha_discover.py --mode momentum --sort score --limit 5 --presentation --narration
python ~/.openclaw/skills/binance-alpha-hunter/tools/alpha_discover.py --mode momentum --sort score --limit 5 --presentation --narration --voice-style neutral
python ~/.openclaw/skills/binance-alpha-hunter/tools/alpha_discover.py --mode momentum --sort score --limit 5 --presentation --narration --voice-style energetic
python ~/.openclaw/skills/binance-alpha-hunter/tools/alpha_discover.py --mode momentum --sort score --limit 5 --presentation --narration --voice-style competition
python ~/.openclaw/skills/binance-alpha-hunter/tools/alpha_discover.py --mode momentum --sort score --limit 5 --presentation --narration --duration 15
python ~/.openclaw/skills/binance-alpha-hunter/tools/alpha_discover.py --mode momentum --sort score --limit 5 --presentation --narration --duration 30
python ~/.openclaw/skills/binance-alpha-hunter/tools/alpha_discover.py --mode momentum --sort score --limit 5 --presentation --narration --duration 60 --voice-style competition
python ~/.openclaw/skills/binance-alpha-hunter/tools/alpha_discover.py --mode momentum --sort score --limit 5 --presentation --narration --voice-style competition --duration 60 --export
python ~/.openclaw/skills/binance-alpha-hunter/tools/alpha_discover.py --mode momentum --sort score --limit 5 --presentation --narration --voice-style competition --duration 60 --export --export-format both
python ~/.openclaw/skills/binance-alpha-hunter/tools/alpha_discover.py --mode momentum --sort score --limit 5 --presentation --narration --voice-style competition --duration 60 --export --export-dir ~/.openclaw/skills/binance-alpha-hunter/exports
python ~/.openclaw/skills/binance-alpha-hunter/tools/alpha_discover.py --competition-mode
```

### 2. 查看风险摘要

```bash
python ~/.openclaw/skills/binance-alpha-hunter/tools/alpha_risk.py UPUSDT
python ~/.openclaw/skills/binance-alpha-hunter/tools/alpha_risk.py ALPHA_804USDT
```

### 3. 生成交易计划

```bash
python ~/.openclaw/skills/binance-alpha-hunter/tools/alpha_plan.py plan UPUSDT --style conservative
python ~/.openclaw/skills/binance-alpha-hunter/tools/alpha_plan.py plan UPUSDT --style aggressive
python ~/.openclaw/skills/binance-alpha-hunter/tools/alpha_plan.py history
python ~/.openclaw/skills/binance-alpha-hunter/tools/alpha_plan.py history --symbol UPUSDT
python ~/.openclaw/skills/binance-alpha-hunter/tools/alpha_plan.py history --limit 5
python ~/.openclaw/skills/binance-alpha-hunter/tools/alpha_plan.py history --summary
```

### 4. 管理 watchlist

```bash
python ~/.openclaw/skills/binance-alpha-hunter/tools/alpha_watchlist.py add UPUSDT --note "观察是否缩量回踩"
python ~/.openclaw/skills/binance-alpha-hunter/tools/alpha_watchlist.py list
python ~/.openclaw/skills/binance-alpha-hunter/tools/alpha_watchlist.py remove UPUSDT
python ~/.openclaw/skills/binance-alpha-hunter/tools/alpha_watchlist.py compare --summary
python ~/.openclaw/skills/binance-alpha-hunter/tools/alpha_watchlist.py compare
```

### 5. paper trade 占位

```bash
python ~/.openclaw/skills/binance-alpha-hunter/tools/alpha_plan.py execute UPUSDT --side buy --amount-usd 100 --style balanced --confirm
```

说明：

- 默认模式是 `paper`
- 不带 `--confirm` 时只会返回需要确认，不会执行
- `spot` / `futures` 真实执行暂未启用，只预留接口形状

## 输出约定

所有脚本默认输出 pretty JSON。

常见字段：

- 候选列表：
  - `symbol`
  - `price`
  - `24h_change`
  - `volume_24h`
  - `tags`
  - `opportunity_score`
  - `reason`
  - `explain`
- 风险摘要：
  - `volatility_risk`
  - `liquidity_risk`
  - `beginner_friendly`
  - `suggested_mode`
  - `risk_flags`
- 交易计划：
  - `entry`
  - `stop_loss`
  - `take_profit`
  - `position_size`
  - `invalidation`
  - `confidence`
  - `plan_reason`
- 稳定性状态：
  - `data_source`
  - `stale`
  - `fetch_warnings`
- paper trade 历史：
  - `trade_id`
  - `symbol`
  - `style`
  - `action`
  - `created_at`
  - `execution_summary`
  - `recent_trade_summary`

如果带 `--presentation`，还会额外返回：

- `title`
- `mode`
- `market_view`
- `top_picks`
- `watch_only`
- `risk_notice`

如果带 `--competition-mode`，会自动启用：

- `presentation`
- `narration`
- `voice_style=competition`
- `duration=60`
- `export`
- `export_format=both`
- `sort=score`

其中 `top_picks[]` 包含：

- `rank`
- `symbol`
- `score`
- `verdict`
- `summary`

如果同时带 `--presentation --narration`，还会额外返回：

- `narration`
- `short_caption`
- `demo_script`
- `voice_style`
- `target_duration_sec`
- `estimated_words`
- `compression_level`
- `tone_notes`
- `use_case`
- `exported_dir`（仅在 `--export` 时返回）
- `latest_submission_dir`（仅在 `--export` 时返回）
- `exported_files`（仅在 `--export` 时返回）

其中 `narration` 至少包含：

- `duration_sec`
- `opening`
- `script`
- `closing`

## Hunter 模式

### `momentum`

- 优先看涨幅、放量、突破、量价同步放大
- 不优先保留明显低流动性的标的

### `safe`

- 优先保留流动性更稳、不过热、对新手更友好的候选
- 更适合“先看稳一点的 Alpha”

### `early`

- 优先看新标的、刚开始放量、刚接近突破的候选
- 更适合早期跟踪而不是无脑追高

### `contrarian`

- 优先看已经有回撤、但成交没有彻底塌掉的标的
- 更适合做反向观察和等待修复

## 展示模式

展示模式适合录屏、比赛演示、投稿截图，不只是给出原始列表，而是额外生成一版中文讲解摘要。

示例：

```bash
python ~/.openclaw/skills/binance-alpha-hunter/tools/alpha_discover.py --mode momentum --sort score --limit 5 --presentation
python ~/.openclaw/skills/binance-alpha-hunter/tools/alpha_discover.py --mode early --sort score --limit 5 --presentation
```

展示模式会补充：

- 当前市场状态一句话总结
- 值得优先讲解的 top picks
- 只适合观察、不适合执行的名单
- 风险提示

如果再加 `--narration`，会额外生成：

- 一段 30-60 秒可直接口播的中文讲稿
- 一条适合发帖或截图配文的短文案
- 一份分段演示提示，方便录屏时照着讲

如果再加 `--voice-style`，可以切换三种中文口播风格：

### `neutral`

- 客观、平稳
- 适合常规产品演示

### `energetic`

- 节奏更快
- 更适合短视频、宣传片段、亮点展示

### `competition`

- 更强调作品价值、机会发现和风控闭环
- 适合比赛投稿、答辩、作品展示

如果再加 `--duration`，可以切三档自动压缩版口播：

### `15`

- 一句市场判断
- 一个重点标的
- 一句风险提示

### `30`

- 市场判断
- 1 到 2 个重点标的
- 观察名单
- 风险提示

### `60`

- 完整版本
- 更适合比赛投稿或正式录屏

## 一键目录包导出

如果加 `--export`，会把当前 discover 结果导出成一个独立目录包，默认根目录是：

- `~/.openclaw/skills/binance-alpha-hunter/exports/`

支持参数：

- `--export`
- `--export-dir`
- `--export-format json|txt|both`

目录名格式：

- `alpha-hunter_{mode}_{voice_style}_{duration}s_{timestamp}/`

目录内当前至少生成：

- `submission.json`
- `voiceover.txt`
- `cover.md`
- `manifest.json`

并且每次导出成功后，还会刷新固定目录：

- `exports/latest_submission/`

其中始终保留最近一次导出的：

- `submission.json`
- `voiceover.txt`
- `cover.md`
- `manifest.json`

`submission.json` 保留完整结构，至少包含：

- `meta`
- `items`
- `presentation`
- `narration`
- `short_caption`
- `demo_script`
- `recent_trade_summary`
- `watchlist_compare_summary`

`manifest.json` 至少包含：

- `package_type`
- `package_version`
- `bundle_name`
- `generated_at`
- `mode`
- `voice_style`
- `duration`
- `ready_for_submission`
- `latest_copy`
- `files`
- `entrypoints`
- `scoreboard`
- `trade_snapshot`
- `trade_history_count`
- `tracking_snapshot`

其中：

- `files`
  - `submission_json`
  - `voiceover_txt`
  - `cover_md`
- `entrypoints`
  - `caption`
  - `narration`
  - `presentation`

`scoreboard` 直接复用现有 `presentation` 摘要，至少包含：

- `market_view`
- `top_picks`
- `watch_only`
- `risk_notice`
- `counts`

其中：

- `top_picks`
  - `rank`
  - `symbol`
  - `score`
  - `verdict`
  - `summary`
- `watch_only`
  - `symbol`
  - `reason`

`trade_snapshot` 轻量保留最近一次 paper trade，至少包含：

- `symbol`
- `style`
- `action`
- `created_at`
- `confidence`
- `execution_summary`

`tracking_snapshot` 轻量保留最近一次 watchlist 对比摘要，至少包含：

- `quick_summary`
- `status_counts`
- `highlights`

其中 `meta` 至少包含：

- `exported_at`
- `mode`
- `voice_style`
- `duration`
- `source`
- `export_version`
- `ready_for_submission`

`voiceover.txt` 当前保留：

- `opening`
- `script`
- `closing`
- `short_caption`

`cover.md` 当前保留：

- 标题
- 导出时间
- mode
- voice_style
- duration
- 一句话作品说明
- 本次市场判断摘要
- top picks 摘要
- watch only 摘要
- 风险提示
- short_caption
- 最近执行摘要
- 最近观察变化
- 文件说明

如果当前没有 paper trade 历史：

- `cover.md` 会写：`暂无 paper trade 历史`
- `manifest.json` 中：
  - `trade_snapshot = null`

如果当前没有可比较的 watchlist 历史：

- `cover.md` 会写：`暂无 watchlist 对比历史`
- `manifest.json` 中：
  - `tracking_snapshot = null`

`manifest.json` 适合：

- 自动化脚本直接读取目录包元信息
- 不解析正文就能知道入口文件和是否可投稿
- 给后续流程统一读取 `caption / narration / presentation` 的入口

另外会在导出根目录下写一份：

- `LATEST.txt`

用于记录最近一次导出的目录路径。

`latest_submission/` 适合：

- 录屏时固定读取最新稿件
- 截图时固定打开最新封面说明
- 后续自动化脚本不需要再解析时间戳目录名

## 网络抖动与缓存回退

Binance 公共接口在比赛演示时可能偶发：

- `SSL: UNEXPECTED_EOF_WHILE_READING`
- timeout
- 临时网络错误
- gzip 解码异常
- JSON 解析异常

当前 skill 已增加：

1. 统一请求封装
2. 自动重试
3. 指数退避 + 少量随机抖动
4. 本地缓存回退

缓存目录：

- `~/.openclaw/skills/binance-alpha-hunter/data/cache/`

当前会缓存最近成功结果，例如：

- `alpha_candidates.json`
- `alpha-exchange-info.json`
- `book-ticker_*.json`
- `klines_*.json`
- `token-meta_*.json`

输出里会显式标注：

- `data_source`
  - `live`
  - `cache_fallback`
- `stale`
  - `true / false`
- `fetch_warnings`
  - 当前请求过程中的降级与重试提示
- `degraded_components`
  - 机器可读的降级组件标识
- `degraded_components_zh`
  - 中文可读的降级组件说明

说明：

- `data_source=cache_fallback` 且 `stale=true` 时，表示本次结果来自最近一次成功缓存
- 这类结果适合比赛演示和旁白连续性，但不应当被误解成百分百实时数据
- 如果有降级组件，导出包和旁白会优先展示中文说明
- 如果没有降级组件，导出包会明确写：`当前没有降级组件`

## Watchlist Compare

`alpha_watchlist.py compare` 用来体现持续观察能力。

当前输出至少包含：

- `score_delta`
- `risk_delta`
- `new_tags`
- `removed_tags`
- `status_change`
- `summary`

并额外提供：

- `quick_summary`
- `status_counts`
- `highlights`

如果只想快速讲解，可以直接用：

```bash
python ~/.openclaw/skills/binance-alpha-hunter/tools/alpha_watchlist.py compare --summary
```

## Demo Runbook

已新增：

- `demo_runbook.md`

建议比赛录屏前先按这个 runbook 走一遍，展示顺序更稳定。

## Paper Trade History

`alpha_plan.py history` 用来查看 paper trade 历史闭环。

支持：

- `history`
- `history --symbol SYMBOL`
- `history --limit N`
- `history --summary`

每次 `execute --confirm` 当前至少会保存：

- `trade_id`
- `symbol`
- `style`
- `action`
- `created_at`
- `entry`
- `stop_loss`
- `take_profit`
- `position_size`
- `invalidation`
- `confidence`
- `plan_reason`
- `risk_report`
- `risk_flags`
- `suggested_mode`
- `opportunity_score`
- `tags`
- `execution_summary`

`history` 当前会输出：

- 全部历史列表
- 按 symbol 过滤
- 最近 N 条
- `quick_summary`
- `recent_trade_summary`

后续如果要把交易历史接进 `cover / presentation / narration`，可以直接复用 `recent_trade_summary`。

## 风险约束

- 这个 skill 默认是研究和计划工具，不是自动交易器
- 没有用户明确确认，不要调用 execute
- 当前版本即便收到“下单”指令，也应优先用 `paper` 返回结构化预执行结果
- 真实 Spot / Futures 接口接入前，不要冒充已支持真实下单
