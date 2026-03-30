"""
themes/trend_scanner.py — Google Trends 掃描器
每週掃描種子關鍵字的搜尋熱度，識別升溫中的主題，
並透過 Related Queries 自動發現新的關聯關鍵字。
"""

import json
import time
import logging
import os
from datetime import datetime

import pandas as pd

import config

logger = logging.getLogger(__name__)

SEEDS_PATH = os.path.join(os.path.dirname(__file__), "keyword_seeds.json")
SCAN_RESULTS_PATH = os.path.join(config.CACHE_DIR, "trends_scan_results.json")


def load_seed_keywords() -> dict:
    """載入種子關鍵字庫"""
    with open(SEEDS_PATH, "r") as f:
        return json.load(f)


def scan_single_keyword(pytrends_client, keyword: str) -> dict:
    """
    掃描單一關鍵字的 Google Trends 數據。

    Returns
    -------
    dict: {
        "keyword": str,
        "acceleration": float,  # 近2週 / 前6週
        "recent_avg": float,
        "baseline_avg": float,
        "current_value": int,
        "related_queries": list[str],
        "status": "rising" | "stable" | "declining" | "error"
    }
    """
    result = {
        "keyword": keyword,
        "acceleration": 0,
        "recent_avg": 0,
        "baseline_avg": 0,
        "current_value": 0,
        "related_queries": [],
        "status": "error",
    }

    try:
        # 取得近 3 個月搜尋熱度
        pytrends_client.build_payload(
            [keyword],
            timeframe=config.TRENDS_TIMEFRAME,
            geo="",  # 全球
        )

        interest = pytrends_client.interest_over_time()

        if interest.empty or keyword not in interest.columns:
            result["status"] = "no_data"
            return result

        values = interest[keyword].values

        if len(values) < 8:
            result["status"] = "insufficient_data"
            return result

        # 計算加速度：近 2 週均值 / 前 6 週均值
        recent = values[-2:]   # 最近 2 個數據點（週線）
        baseline = values[-8:-2]  # 前 6 個數據點

        recent_avg = float(recent.mean())
        baseline_avg = float(baseline.mean())

        if baseline_avg > 0:
            acceleration = recent_avg / baseline_avg
        elif recent_avg > 0:
            acceleration = 3.0  # 從零起步，給高加速度
        else:
            acceleration = 0

        result["recent_avg"] = round(recent_avg, 1)
        result["baseline_avg"] = round(baseline_avg, 1)
        result["acceleration"] = round(acceleration, 2)
        result["current_value"] = int(values[-1])

        if acceleration >= config.TRENDS_ACCELERATION_THRESHOLD:
            result["status"] = "rising"
        elif acceleration >= 0.8:
            result["status"] = "stable"
        else:
            result["status"] = "declining"

        # 取得相關查詢（發現新關鍵字）
        try:
            related = pytrends_client.related_queries()
            if keyword in related and related[keyword].get("rising") is not None:
                rising_df = related[keyword]["rising"]
                if not rising_df.empty and "query" in rising_df.columns:
                    result["related_queries"] = rising_df["query"].head(5).tolist()
        except Exception:
            pass  # Related queries 失敗不影響主流程

    except Exception as e:
        logger.warning(f"  ⚠️ '{keyword}' 掃描失敗: {e}")
        result["status"] = "error"

    return result


def scan_all_themes() -> dict:
    """
    掃描所有種子關鍵字，回傳完整掃描結果。

    Returns
    -------
    dict: {
        "scan_date": str,
        "rising_themes": [
            {
                "category": str,
                "keyword": str,
                "acceleration": float,
                "related_queries": list,
                ...
            }
        ],
        "all_results": [...],
        "new_discoveries": list[str],
    }
    """
    from pytrends.request import TrendReq

    logger.info("🌐 開始 Google Trends 掃描...")

    pytrends = TrendReq(hl="en-US", tz=360, timeout=(10, 30))
    seeds = load_seed_keywords()

    all_results = []
    rising_themes = []
    new_discoveries = []
    total_keywords = sum(len(v) for v in seeds.values())
    scanned = 0

    for category, keywords in seeds.items():
        logger.info(f"  📂 {category} ({len(keywords)} 個關鍵字)")

        for keyword in keywords:
            scanned += 1
            logger.info(f"    [{scanned}/{total_keywords}] {keyword}")

            result = scan_single_keyword(pytrends, keyword)
            result["category"] = category
            all_results.append(result)

            if result["status"] == "rising":
                rising_themes.append(result)
                logger.info(
                    f"    🔺 升溫! 加速度: {result['acceleration']:.1f}x"
                )

                # 收集新發現的關聯查詢
                for rq in result.get("related_queries", []):
                    # 過濾掉已在種子庫中的
                    all_seeds_flat = [
                        kw.lower() for kws in seeds.values() for kw in kws
                    ]
                    if rq.lower() not in all_seeds_flat:
                        new_discoveries.append(rq)

            # 控制查詢頻率
            time.sleep(config.TRENDS_QUERY_DELAY)

    # 去重新發現
    new_discoveries = list(set(new_discoveries))

    scan_result = {
        "scan_date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "total_scanned": scanned,
        "rising_count": len(rising_themes),
        "rising_themes": rising_themes,
        "all_results": all_results,
        "new_discoveries": new_discoveries[:20],  # 最多保留 20 個
    }

    # 儲存掃描結果
    try:
        with open(SCAN_RESULTS_PATH, "w") as f:
            json.dump(scan_result, f, indent=2, ensure_ascii=False)
        logger.info(f"💾 掃描結果已儲存")
    except Exception as e:
        logger.warning(f"掃描結果儲存失敗: {e}")

    logger.info(
        f"✅ 掃描完成: {scanned} 個關鍵字, "
        f"{len(rising_themes)} 個升溫主題, "
        f"{len(new_discoveries)} 個新發現"
    )

    return scan_result


def get_rising_themes() -> list:
    """
    取得最近一次掃描的升溫主題（從快取讀取）。
    如果快取不存在或過期（> 10 天），回傳空列表。
    """
    if not os.path.exists(SCAN_RESULTS_PATH):
        return []

    try:
        # 檢查是否過期
        mod_time = datetime.fromtimestamp(os.path.getmtime(SCAN_RESULTS_PATH))
        if (datetime.now() - mod_time).days > 10:
            logger.info("⚠️ Trends 掃描結果已過期（> 10 天）")
            return []

        with open(SCAN_RESULTS_PATH, "r") as f:
            data = json.load(f)
        return data.get("rising_themes", [])
    except Exception:
        return []
