# Binance Alpha Hunter Demo Prompts

## discover_alpha

- 用 `Binance Alpha Hunter` 帮我找 10 个 Binance Alpha 候选，按 24h 成交量排序。
- 帮我筛一下最近比较热的 Alpha 候选，优先看带热门标签的。
- 给我列出最近新上的 Binance Alpha 标的。
- 用 momentum 模式给我列 5 个最强 Alpha Hunter 候选，并解释为什么入选。
- 用 safe 模式找 5 个更适合新手观察的 Binance Alpha 标的。
- 用 early 模式找 5 个可能刚启动的新 Alpha 标的，重点看新标的和放量。
- 用 contrarian 模式找 5 个回撤后还值得盯盘的 Alpha 标的。
- 给我按 opportunity_score 从高到低排一个 Alpha Hunter 榜单。
- 用展示模式输出一版适合比赛录屏的 Binance Alpha Hunter 榜单，要包含市场一句话判断、top picks、watch only 和风险提示。
- 给我一版能直接念出来的 Alpha Hunter 展示摘要，模式用 momentum。
- 用 early 模式生成演示稿风格的榜单摘要，告诉我哪些可以讲、哪些只适合观察。
- 用 presentation + narration 模式给我生成一版 30-60 秒中文口播稿，我要直接拿去录屏。
- 给我一版适合比赛投稿的 Binance Alpha Hunter 旁白稿，同时附 short caption 和 demo_script。
- 用 momentum 模式做一版旁白稿，结构要包含市场判断、top picks、watch only 和风险提示。
- 用 neutral 风格给我生成一版常规产品演示旁白稿。
- 用 energetic 风格给我生成一版更有节奏感的短视频口播稿。
- 用 competition 风格给我生成一版适合比赛投稿的旁白稿，突出机会发现和风控闭环。
- 给我一版 15 秒压缩口播，只要市场判断、一个重点标的和一句风险提示。
- 给我一版 30 秒演示口播，适合常规录屏。
- 给我一版 60 秒 competition 风格口播，适合比赛投稿或正式作品展示。
- 直接用 competition_mode 给我生成完整比赛包，我不想自己拼参数。
- 把这次 Alpha Hunter 结果直接导出成一键目录包。
- 这次结果帮我导出到 exports 目录，生成 submission.json、voiceover.txt 和 cover.md，我要直接拿去录屏和截图。
- 用 competition 风格、60 秒版本生成一份可投稿的一键目录包。
- 导出完成后顺便刷新 latest_submission，我后面要直接从固定目录拿最新稿件。
- 帮我生成一份目录包，并把最新版本覆盖到 latest_submission，方便我继续录屏。
- 导出时顺便生成 manifest.json，我后面的自动化脚本只读 manifest。
- 帮我确认时间戳目录和 latest_submission 里都带 manifest.json。
- manifest.json 里顺便带上 scoreboard，我后续脚本直接读 top picks 和 watch only。
- 帮我确认 manifest.json 里的 scoreboard 能直接读 market_view、top_picks、watch_only 和 risk_notice。
- 导出比赛包时顺便带上 recent_trade_summary，我想把最近一次执行闭环也展示出来。
- 帮我确认 cover.md 里已经有最近执行摘要，没有历史时要优雅显示。
- 导出比赛包时把 data_source / stale / fetch_warnings 也写进去，我想让评审看到数据新鲜度。
- 帮我确认 cover.md 里已经有数据状态板块，没有告警时要写“当前数据链路正常”。
- 如果发生缓存回退，帮我把 degraded_components 转成中文说明，一起写进导出包和旁白稿。
- 对比当前 watchlist 和上次结果，给我一个 quick summary。
- 帮我看 watchlist 里哪些标的转强了、哪些转弱了，给出 score_delta 和 risk_delta。

## get_risk_report

- 用 `Binance Alpha Hunter` 看一下 `UPUSDT` 的风险摘要。
- 帮我判断 `ALPHA_804USDT` 是否适合新手。
- 分析这个 Alpha 币的波动风险和流动性风险：`SN3USDT`
- 给我这个标的的 risk_flags，并告诉我为什么现在更适合观望还是计划交易。

## make_trade_plan

- 用 conservative 风格给 `UPUSDT` 生成交易计划。
- 给 `SN3USDT` 做一个 balanced 的交易计划。
- 如果我偏激进，`UPUSDT` 应该怎么设 entry、stop loss、take profit？
- 给我一个带 confidence 和 plan_reason 的 balanced 交易计划，适合拿来比赛演示。
- 如果这个标的 risk_flags 里有 overheated，就把计划做得更保守一点并说明原因。
- 给我看 paper trade 全部历史。
- 只看 `UPUSDT` 的 paper trade 历史。
- 给我最近 5 条 paper trade，并附 quick summary。
- 给我一个只看摘要版的 paper trade history。

## watchlist

- 把 `UPUSDT` 加入 watchlist，备注“等回踩”。
- 从 watchlist 删除 `SN3USDT`。
- 列出当前的 Alpha watchlist。

## execute_trade

- 先给我一个 paper trade 版本的 `UPUSDT buy 100U` 预执行。
- 我确认执行，按 balanced 计划对 `UPUSDT` 做一笔 paper trade。
- 先不要真实下单，只做 paper trade 记录。
- 先给我完整的计划和风险理由，再等我确认后只做 paper trade。
