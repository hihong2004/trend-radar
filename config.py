"""
config.py — 全域設定
評分權重、閾值、API keys、標的清單、快取路徑
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── API Keys ──────────────────────────────────────────────
FRED_API_KEY = os.getenv("FRED_API_KEY", "")
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
LINE_USER_ID = os.getenv("LINE_USER_ID", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# ── LINE API ──────────────────────────────────────────────
LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"

# ── 基準標的 ──────────────────────────────────────────────
BENCHMARK = "SPY"

# ── 產業 ETF 對照表 ───────────────────────────────────────
SECTOR_ETFS = {
    "Technology": "XLK",
    "Semiconductors & Semiconductor Equipment": "SMH",
    "Communication Services": "XLC",
    "Health Care": "XLV",
    "Financials": "XLF",
    "Energy": "XLE",
    "Industrials": "XLI",
    "Consumer Discretionary": "XLY",
    "Consumer Staples": "XLP",
    "Utilities": "XLU",
    "Real Estate": "XLRE",
    "Materials": "XLB",
}

# 額外追蹤的細分產業 ETF
SUB_SECTOR_ETFS = {
    "Software": "IGV",
    "Biotech": "XBI",
    "Clean Energy": "ICLN",
}

ALL_SECTOR_ETFS = {**SECTOR_ETFS, **SUB_SECTOR_ETFS}

# ── 評分權重 ──────────────────────────────────────────────
SCORING_WEIGHTS = {
    "relative_strength": 0.22,
    "price_structure": 0.18,
    "volume_analysis": 0.18,
    "volatility": 0.12,
    "sector_momentum": 0.10,
    "trend_consistency": 0.10,
    "theme_momentum": 0.10,
}

# ── 等級劃分 ──────────────────────────────────────────────
RATING_THRESHOLDS = {
    5: 85,   # ★★★★★
    4: 70,   # ★★★★☆
    3: 55,   # ★★★☆☆
    2: 40,   # ★★☆☆☆
    1: 0,    # ★☆☆☆☆
}

# ── Stage 判定參數 ────────────────────────────────────────
STAGE_PARAMS = {
    "awakening_threshold": 55,       # 總分 >= 此值進入 Stage 1
    "acceleration_threshold": 70,    # 總分 >= 此值進入 Stage 2
    "acceleration_hold_days": 10,    # 需持續 N 天
    "sector_confirm_threshold": 60,  # 族群共振需 >= 此值
    "decay_drop_points": 15,         # 從高點回落超過此值 → Stage 3
    "rs_decay_percentile": 50,       # RS 跌出 top N% → Stage 3
}

# ── 數據參數 ──────────────────────────────────────────────
DATA_HISTORY_YEARS = 2              # 下載多少年歷史數據
DATA_BATCH_SIZE = 55                # 每批下載幾檔
DATA_BATCH_DELAY = 2                # 每批之間延遲秒數
INCREMENTAL_DAYS = 10               # 增量更新天數

# ── Google Trends 參數 ────────────────────────────────────
TRENDS_TIMEFRAME = "today 3-m"      # 近 3 個月
TRENDS_ACCELERATION_THRESHOLD = 1.5 # 加速度閾值
TRENDS_QUERY_DELAY = 3              # 每次查詢間隔秒數

# ── Claude API 參數 ───────────────────────────────────────
CLAUDE_MODEL = "claude-sonnet-4-20250514"
CLAUDE_MAX_TOKENS = 1000
THEME_CACHE_DAYS = 30               # 映射結果快取天數

# ── 快取路徑 ──────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(BASE_DIR, "cache")
SCORES_DIR = os.path.join(CACHE_DIR, "scores")
os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(SCORES_DIR, exist_ok=True)
