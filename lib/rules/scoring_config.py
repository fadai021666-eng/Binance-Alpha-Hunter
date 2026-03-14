"""发现打分的可配置阈值，消除 magic numbers。"""

SCORE_CONFIG = {
    "base_score": 35,
    "change_24h": {
        "strong_up": {"range": (4, 18), "bonus": 12},
        "very_strong_up": {"range": (18, 35), "bonus": 16},
        "weak_up": {"range": (0, 4), "bonus": 5},
        "mild_down": {"range": (-12, 0), "bonus": -4},
        "deep_down": {"range": (-999, -12), "bonus": -12},
    },
    "volume_percentile_weight": 18,
    "synchronized_expansion_bonus": 12,
    "new_listing_bonus": 8,
    "price_breakout_bonus": 8,
    "illiquid_penalty": -15,
    "overheated_penalty": -12,
    "short_term_dump_penalty": -6,  # return_5m < -0.03
    "short_term_dump_threshold": -0.03,
}

ILLIQUID_THRESHOLDS = {
    "min_liquidity": 500_000,
    "min_liquidity_percentile": 0.22,
    "min_volume": 800_000,
}

OVERHEATED_THRESHOLDS = {
    "max_change_24h": 35,
    "max_return_5m_with_spike": 0.04,
}

SYNCHRONIZED_EXPANSION_THRESHOLDS = {
    "min_change_24h": 8,
    "min_return_15m": 0.02,
}

NEW_LISTING_WATCH_ONLY_PERCENTILE = 0.35
