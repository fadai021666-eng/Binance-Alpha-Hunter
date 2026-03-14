# Binance Alpha Hunter Demo Runbook

## 作品定位

这是一个面向 Binance AI Agent 投稿场景的 Alpha Hunter 作品。

它不只是输出榜单，还把：

- 候选发现
- 风险解释
- 交易计划
- 中文旁白
- 投稿导出
- 持续跟踪

串成一条完整展示链路。

## 推荐第一步

直接跑一键比赛模式：

```bash
python ~/.openclaw/skills/binance-alpha-hunter/tools/alpha_discover.py --competition-mode
```

这会自动启用：

- `presentation`
- `narration`
- `voice_style=competition`
- `duration=60`
- `export`
- `export_format=both`
- `sort=score`

## 推荐演示顺序

### 1. 打开最新投稿目录

优先看：

- `exports/latest_submission/cover.md`
- `exports/latest_submission/voiceover.txt`
- `exports/latest_submission/manifest.json`

并确认：

- `cover.md` 里已有“数据状态”
- 如有降级组件，会用中文直接写明
- 如无降级，会写“当前数据链路正常”

### 2. 讲榜单

重点讲：

- `market_view`
- `top_picks`
- `watch_only`
- `risk_notice`

### 3. 讲旁白与导出

说明这个作品不仅会发现标的，还会：

- 自动生成中文旁白
- 自动整理投稿目录
- 自动维护 latest_submission 固定副本

## 持续跟踪演示

### 1. 先加入 watchlist

```bash
python ~/.openclaw/skills/binance-alpha-hunter/tools/alpha_watchlist.py add LABUSDT --note "比赛演示样例"
```

### 2. 首次对比

```bash
python ~/.openclaw/skills/binance-alpha-hunter/tools/alpha_watchlist.py compare --summary
```

### 3. 后续再次对比

```bash
python ~/.openclaw/skills/binance-alpha-hunter/tools/alpha_watchlist.py compare
```

重点看：

- `score_delta`
- `risk_delta`
- `new_tags`
- `removed_tags`
- `status_change`
- `summary`

## 收尾口径

- 这个作品不是单点功能，而是完整参赛展示链路
- 下一步如果接 Binance testnet，就能从研究型 agent 往执行型 agent 继续推进
