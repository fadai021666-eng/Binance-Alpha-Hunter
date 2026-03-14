# Binance Alpha Hunter

一个面向 **Binance Alpha** 场景的 **OpenClaw Skill**。  
它不是单纯的行情查询工具，也不是只会给榜单的数据脚本，而是一个更像 **Alpha Hunter Agent** 的完整闭环：

**发现机会 → 风险判断 → 交易计划 → Paper Trade → 持续跟踪 → 比赛包导出**

---

## 这个项目解决什么问题

Binance Alpha 场景下，用户通常会连续做几件事：

- 找值得关注的候选标的
- 判断是不是只是热度高，还是确实有跟踪价值
- 根据风险偏好生成执行计划
- 记录一次模拟执行结果
- 对比下一轮观察时，哪些标的转强、哪些转弱
- 把结果整理成适合录屏、投稿、展示的内容

**Binance Alpha Hunter** 的目标，就是把这条链路做成一个可复用的 Skill，而不是把这些步骤拆成多个零散脚本。

---

## 核心能力

### 1. 机会发现
- 发现 Binance Alpha 候选标的
- 基于机会分、标签和解释输出 top picks
- 支持不同筛选模式：
  - `momentum`
  - `safe`
  - `early`
  - `contrarian`

### 2. 风险判断
- 输出波动风险、流动性风险和新手适配度
- 给出建议模式：
  - `watch`
  - `spot`
  - `futures`

### 3. 交易计划
- 支持：
  - `conservative`
  - `balanced`
  - `aggressive`
- 输出：
  - entry
  - stop loss
  - take profit
  - position size
  - invalidation
  - confidence
  - plan_reason

### 4. Paper Trade 闭环
- 支持模拟执行
- 自动保留执行快照
- 支持历史记录和 recent trade summary

### 5. Watchlist 跟踪
- 支持 add / remove / list / compare
- 可以跟踪：
  - `score_delta`
  - `risk_delta`
  - `status_change`
  - `highlights`

### 6. 比赛展示与导出
- 支持 `presentation`
- 支持 `narration`
- 支持 `competition_mode`
- 自动导出：
  - `submission.json`
  - `voiceover.txt`
  - `cover.md`
  - `manifest.json`

---

## 为什么它不像普通榜单工具

这个项目最核心的设计，不是“多给几个行情字段”，而是强调三条闭环：

### 发现闭环
从候选中筛出真正值得看的标的，而不是简单罗列结果。

### 执行闭环
不仅给计划，还支持 paper trade，并保留执行前后的理由快照。

### 跟踪闭环
不仅告诉你“现在谁值得看”，还会告诉你“和上一次比，谁在转强，谁在转弱”。

---

## 一键比赛模式

如果你只想快速看到完整作品输出，直接运行：

```bash
python ~/.openclaw/skills/binance-alpha-hunter/tools/alpha_discover.py --competition-mode
```

它会自动启用：

- `presentation`
- `narration`
- `voice_style=competition`
- `duration=60`
- `export`
- `export_format=both`
- `sort=score`

并自动生成完整比赛包。

## 导出结果

运行 `--competition-mode` 后，导出目录中会包含：

- `submission.json`：完整结构化结果
- `voiceover.txt`：可直接录屏念稿
- `cover.md`：比赛展示说明页
- `manifest.json`：自动化读取入口

同时会刷新：

- `exports/LATEST.txt`
- `exports/latest_submission/`

---

## 数据状态与稳定性

为了让演示链路更稳，项目补了这些机制：

- 自动重试
- gzip / JSON 解码容错
- 本地缓存回退
- `data_source`
- `stale`
- `fetch_warnings`
- `degraded_components`

即使 Binance 公共接口有瞬时波动，也尽量保证 discover、competition mode 和导出链路不中断。

---

## 项目结构

```text
binance-alpha-hunter/
  SKILL.md
  README.md
  LICENSE
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
    output.py
    paper_trades.py
    watchlist.py
    rules/
  data/
    watchlist.json
  examples/
    demo_prompts.md
  demo_runbook.md
```

## 常用命令

### 发现候选

```bash
python ~/.openclaw/skills/binance-alpha-hunter/tools/alpha_discover.py --limit 10 --sort volume
python ~/.openclaw/skills/binance-alpha-hunter/tools/alpha_discover.py --mode momentum --sort score --limit 8
python ~/.openclaw/skills/binance-alpha-hunter/tools/alpha_discover.py --mode safe --sort score --limit 8
```

### 风险摘要

```bash
python ~/.openclaw/skills/binance-alpha-hunter/tools/alpha_risk.py UPUSDT
python ~/.openclaw/skills/binance-alpha-hunter/tools/alpha_risk.py ALPHA_804USDT
```

### 交易计划与 Paper Trade

```bash
python ~/.openclaw/skills/binance-alpha-hunter/tools/alpha_plan.py plan UPUSDT --style balanced
python ~/.openclaw/skills/binance-alpha-hunter/tools/alpha_plan.py execute UPUSDT --side buy --amount-usd 100 --style balanced --confirm
python ~/.openclaw/skills/binance-alpha-hunter/tools/alpha_plan.py history --summary
```

### Watchlist 跟踪

```bash
python ~/.openclaw/skills/binance-alpha-hunter/tools/alpha_watchlist.py add UPUSDT --note "观察是否缩量回踩"
python ~/.openclaw/skills/binance-alpha-hunter/tools/alpha_watchlist.py compare --summary
```

### 录屏与比赛演示

```bash
python ~/.openclaw/skills/binance-alpha-hunter/tools/alpha_discover.py --competition-mode
```

建议正式录屏前再看一遍：

- `demo_runbook.md`
