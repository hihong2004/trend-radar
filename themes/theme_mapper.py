"""
themes/theme_mapper.py — 主題→企業映射
使用 Claude API 將升溫的產業主題自動映射到 S&P 500 / Nasdaq 100 中的關聯企業。
映射結果快取至 theme_cache.json，同一主題 30 天內不重複呼叫。
"""

import json
import logging
import os
from datetime import datetime, timedelta

import config

logger = logging.getLogger(__name__)

THEME_CACHE_PATH = os.path.join(os.path.dirname(__file__), "theme_cache.json")
THEME_GROUPS_PATH = os.path.join(os.path.dirname(__file__), "theme_groups.json")


def _load_cache() -> dict:
    """載入映射快取"""
    if os.path.exists(THEME_CACHE_PATH):
        try:
            with open(THEME_CACHE_PATH, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_cache(cache: dict):
    """儲存映射快取"""
    try:
        with open(THEME_CACHE_PATH, "w") as f:
            json.dump(cache, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"快取儲存失敗: {e}")


def _is_cache_valid(cache_entry: dict) -> bool:
    """檢查快取是否在有效期內"""
    cached_date = cache_entry.get("cached_date", "")
    if not cached_date:
        return False
    try:
        dt = datetime.strptime(cached_date, "%Y-%m-%d")
        return (datetime.now() - dt).days < config.THEME_CACHE_DAYS
    except Exception:
        return False


def map_theme_via_claude(keyword: str, category: str, acceleration: float) -> dict:
    """
    使用 Claude API 將主題關鍵字映射到關聯企業。

    Parameters
    ----------
    keyword : 升溫中的關鍵字
    category : 所屬主題分類
    acceleration : Google Trends 加速度

    Returns
    -------
    dict: {
        "theme": str,
        "tickers": list[str],
        "reasoning": str,
        "source": "claude_api",
        "cached_date": str,
    }
    """
    if not config.ANTHROPIC_API_KEY:
        logger.warning("ANTHROPIC_API_KEY 未設定，無法使用 Claude API 映射")
        return _fallback_mapping(keyword, category)

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

        system_prompt = (
            "你是一位美股產業分析師。用戶會給你一個正在升溫的產業主題關鍵字。"
            "請從 S&P 500 和 Nasdaq 100 成分股中，找出最直接受惠的企業。"
            "只回傳 JSON，不要任何其他文字或 markdown 標記。"
            "格式：{\"theme\": \"主題名稱\", \"tickers\": [\"TICKER1\", \"TICKER2\"], "
            "\"reasoning\": \"簡述為什麼這些企業受惠\"}"
            "\n只列出真正直接受惠的企業（5-15 檔），不要硬湊。"
            "Ticker 必須是在美國交易所上市的有效股票代號。"
        )

        user_prompt = (
            f"正在升溫的主題：{keyword}\n"
            f"分類：{category}\n"
            f"Google Trends 加速度：{acceleration:.1f}x\n"
            f"請映射到相關的 S&P 500 / Nasdaq 100 成分股。"
        )

        response = client.messages.create(
            model=config.CLAUDE_MODEL,
            max_tokens=config.CLAUDE_MAX_TOKENS,
            messages=[{"role": "user", "content": user_prompt}],
            system=system_prompt,
        )

        # 解析回應
        text = response.content[0].text.strip()

        # 清理可能的 markdown 標記
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        result = json.loads(text)
        result["source"] = "claude_api"
        result["cached_date"] = datetime.now().strftime("%Y-%m-%d")
        result["keyword"] = keyword
        result["category"] = category

        logger.info(
            f"  🤖 Claude 映射: {keyword} → {result.get('tickers', [])}"
        )
        return result

    except json.JSONDecodeError as e:
        logger.error(f"  Claude API 回傳的 JSON 解析失敗: {e}")
        return _fallback_mapping(keyword, category)
    except Exception as e:
        logger.error(f"  Claude API 呼叫失敗: {e}")
        return _fallback_mapping(keyword, category)


def _fallback_mapping(keyword: str, category: str) -> dict:
    """
    當 Claude API 不可用時的備用映射。
    使用內建的基礎映射表。
    """
    fallback_map = {
        "AI_Infrastructure": ["NVDA", "AMD", "AVGO", "SMCI", "DELL", "MRVL"],
        "Semiconductors": ["NVDA", "AMD", "INTC", "AVGO", "QCOM", "TXN", "LRCX", "AMAT", "KLAC", "ASML"],
        "Optical_Communication": ["COHR", "LITE", "MRVL", "AVGO", "CSCO"],
        "Energy_Grid": ["GE", "ETN", "EMR", "AES", "NEE", "VST", "CEG"],
        "Biotech_Pharma": ["LLY", "NVO", "AMGN", "VRTX", "REGN", "GILD", "MRNA"],
        "Quantum_Computing": ["GOOG", "IBM", "IONQ", "RGTI", "MSFT"],
        "Robotics_Automation": ["ISRG", "ROK", "TER", "FANUY", "ABB"],
        "Cybersecurity": ["CRWD", "PANW", "FTNT", "ZS", "S"],
        "Space_Defense": ["LMT", "RTX", "NOC", "GD", "BA", "RKLB"],
        "Fintech_Crypto": ["COIN", "SQ", "PYPL", "MSTR", "V", "MA"],
        "Cloud_SaaS": ["MSFT", "AMZN", "GOOG", "CRM", "NOW", "SNOW"],
        "EV_Battery": ["TSLA", "RIVN", "LI", "ALB", "PANW"],
        "Clean_Energy": ["ENPH", "SEDG", "FSLR", "NEE", "RUN"],
        "Real_Estate": ["DLR", "EQIX", "AMT", "PLD", "SPG"],
        "Healthcare_Tech": ["ISRG", "DXCM", "VEEV", "TDOC", "HIMS"],
        "Commodity_Resources": ["FCX", "NEM", "CCJ", "MP", "BHP"],
        "Consumer_Trends": ["NFLX", "DIS", "DKNG", "SPOT", "LVMUY"],
    }

    tickers = fallback_map.get(category, [])

    return {
        "theme": keyword,
        "tickers": tickers,
        "reasoning": f"備用映射（{category} 分類預設）",
        "source": "fallback",
        "cached_date": datetime.now().strftime("%Y-%m-%d"),
        "keyword": keyword,
        "category": category,
    }


def map_rising_themes(rising_themes: list) -> list:
    """
    對所有升溫主題進行企業映射。
    優先使用快取，快取過期才呼叫 Claude API。

    Parameters
    ----------
    rising_themes : list of dicts from trend_scanner

    Returns
    -------
    list of mapping dicts with tickers
    """
    cache = _load_cache()
    mappings = []

    for theme in rising_themes:
        keyword = theme["keyword"]
        category = theme.get("category", "")
        acceleration = theme.get("acceleration", 0)

        # 檢查快取
        cache_key = keyword.lower().strip()
        if cache_key in cache and _is_cache_valid(cache[cache_key]):
            logger.info(f"  📦 快取命中: {keyword}")
            mapping = cache[cache_key]
            # 更新加速度（快取的可能是舊值）
            mapping["acceleration"] = acceleration
            mappings.append(mapping)
            continue

        # 呼叫 Claude API
        logger.info(f"  🔄 映射: {keyword}")
        mapping = map_theme_via_claude(keyword, category, acceleration)
        mapping["acceleration"] = acceleration

        # 存入快取
        cache[cache_key] = mapping
        mappings.append(mapping)

    # 儲存快取
    _save_cache(cache)

    return mappings


def update_theme_groups(mappings: list):
    """
    更新 theme_groups.json，這是評分模組讀取的檔案。

    將映射結果整合、去重，更新主題狀態。
    """
    # 載入現有群組
    existing = {"active_themes": [], "cooling_themes": []}
    if os.path.exists(THEME_GROUPS_PATH):
        try:
            with open(THEME_GROUPS_PATH, "r") as f:
                existing = json.load(f)
        except Exception:
            pass

    # 現有活躍主題的 keyword set
    existing_keywords = {
        t.get("keyword", t.get("theme", "")).lower()
        for t in existing.get("active_themes", [])
    }

    active_themes = []
    seen_keywords = set()

    for m in mappings:
        keyword = m.get("keyword", m.get("theme", ""))
        key = keyword.lower().strip()

        if key in seen_keywords:
            continue
        seen_keywords.add(key)

        theme_entry = {
            "theme": m.get("theme", keyword),
            "keyword": keyword,
            "category": m.get("category", ""),
            "acceleration": m.get("acceleration", 0),
            "status": "rising" if m.get("acceleration", 0) >= config.TRENDS_ACCELERATION_THRESHOLD else "stable",
            "tickers": m.get("tickers", []),
            "reasoning": m.get("reasoning", ""),
            "source": m.get("source", ""),
            "first_detected": m.get("cached_date", datetime.now().strftime("%Y-%m-%d")),
        }
        active_themes.append(theme_entry)

    # 把之前活躍但這次沒出現的主題移到 cooling
    cooling_themes = existing.get("cooling_themes", [])
    for old_theme in existing.get("active_themes", []):
        old_key = old_theme.get("keyword", old_theme.get("theme", "")).lower()
        if old_key not in seen_keywords:
            old_theme["status"] = "cooling"
            old_theme["acceleration"] = old_theme.get("acceleration", 1.0) * 0.8
            cooling_themes.append(old_theme)

    # 只保留最近 30 天的 cooling 主題
    cooling_themes = [
        t for t in cooling_themes
        if t.get("acceleration", 0) > 0.3
    ][:20]

    # 組合結果
    output = {
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "active_themes": active_themes,
        "cooling_themes": cooling_themes,
    }

    try:
        with open(THEME_GROUPS_PATH, "w") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        logger.info(
            f"✅ 主題群組已更新: "
            f"{len(active_themes)} 活躍, {len(cooling_themes)} 降溫"
        )
    except Exception as e:
        logger.error(f"主題群組儲存失敗: {e}")

    return output


def run_theme_discovery() -> dict:
    """
    完整的主題發現流程：
    1. Google Trends 掃描
    2. 識別升溫主題
    3. Claude API 映射
    4. 更新 theme_groups.json
    """
    from themes.trend_scanner import scan_all_themes

    logger.info("=" * 50)
    logger.info("🌐 開始主題自動發現...")
    logger.info("=" * 50)

    # Step 1: 掃描 Google Trends
    scan_result = scan_all_themes()
    rising = scan_result.get("rising_themes", [])

    if not rising:
        logger.info("📭 沒有發現升溫主題")
        # 即使沒有新主題，也要更新狀態（把舊主題標記為 cooling）
        update_theme_groups([])
        return scan_result

    logger.info(f"🔥 發現 {len(rising)} 個升溫主題，開始映射...")

    # Step 2: 映射到企業
    mappings = map_rising_themes(rising)

    # Step 3: 更新主題群組
    groups = update_theme_groups(mappings)

    # 補充新發現到掃描結果
    scan_result["mappings"] = mappings
    scan_result["theme_groups"] = groups

    logger.info("🏁 主題發現完成")
    return scan_result
