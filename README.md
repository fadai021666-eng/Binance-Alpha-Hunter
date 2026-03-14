# Binance Alpha Hunter

面向 **Binance Alpha** 场景的 OpenClaw Skill —— 不是单纯的行情查询，而是一个完整闭环：

**发现机会 → 风险判断 → 交易计划 → Paper Trade → 持续跟踪 → 比赛包导出**

---

## 快速开始

```bash
# 一键比赛模式（自动启用展示、旁白、导出）
python tools/alpha_discover.py --competition-mode

# 发现候选
python tools/alpha_discover.py --limit 5 --sort volume
python tools/alpha_discover.py --mode safe --sort score --limit 8

# 风险摘要
python tools/alpha_risk.py UPUSDT

# 交易计划
python tools/alpha_plan.py plan UPUSDT --style balanced

# Paper Trade
python tools/alpha_plan.py execute UPUSDT --side buy --amount-usd 100 --style balanced --confirm
python tools/alpha_plan.py history --summary

# Watchlist
python tools/alpha_watchlist.py add UPUSDT --note "观察缩量回踩"
python tools/alpha_watchlist.py compare --summary
```

## 核心能力

| 能力 | 说明 |
|------|------|
| 机会发现 | 4 种模式：`momentum` / `safe` / `early` / `contrarian` |
| 风险判断 | 波动风险、流动性风险、新手适配度、建议模式 |
| 交易计划 | 3 种风格：`conservative` / `balanced` / `aggressive` |
| Paper Trade | 模拟执行 + 历史记录 + 摘要 |
| Watchlist | add / remove / list / compare，跟踪 score_delta 和 status_change |
| 比赛导出 | `submission.json` / `voiceover.txt` / `cover.md` / `manifest.json` |

## 项目结构

```
binance-alpha-hunter/
  SKILL.md                  # OpenClaw skill 定义
  README.md
  pyproject.toml
  lib/
    __init__.py
    binance_alpha.py        # Binance API 封装（重试 + 缓存回退）
    types.py                # AlphaCandidate 数据模型
    output.py               # 统一 JSON 渲染
    paper_trades.py         # Paper trade 持久化
    watchlist.py            # Watchlist 持久化与对比
    rules/
      __init__.py           # 统一 re-export
      discover.py           # 发现打分
      risk.py               # 风险评估
      trade_plan.py         # 交易计划生成
      presentation.py       # 展示摘要与旁白
      scoring_config.py     # 打分阈值配置
  tools/
    alpha_discover.py       # CLI: 发现 + 展示 + 导出
    alpha_risk.py           # CLI: 单标的风险
    alpha_plan.py           # CLI: 计划 + 执行 + 历史
    alpha_watchlist.py      # CLI: watchlist 管理
  tests/                    # pytest 测试
  data/
    cache/                  # API 缓存（gitignore）
  exports/                  # 导出包（gitignore）
```

## 数据稳定性

- 自动重试 + 指数退避
- gzip / JSON 解码容错
- 本地缓存回退（`data_source` / `stale` / `fetch_warnings` / `degraded_components`）

即使 Binance 接口瞬时波动，discover 和 competition mode 也不会中断。

## 风险提示

- 默认是研究和计划工具，不是自动交易器
- 没有用户明确确认，不会执行交易
- 当前版本只支持 paper trade，Spot / Futures 接口只预留形状
