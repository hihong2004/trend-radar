"""
universe.py — 取得 S&P 500 + Nasdaq 100 成分股清單
從 Wikipedia 抓取成分股列表，去重合併，並取得 GICS Sector 分類。
如果 Wikipedia 被擋（403），使用備用方案。
"""

import logging
import pandas as pd
import json
import os
import requests
from datetime import datetime

import config

logger = logging.getLogger(__name__)

UNIVERSE_CACHE = os.path.join(config.CACHE_DIR, "universe.json")

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def _read_html_with_headers(url: str) -> list:
    """用自定義 headers 抓取網頁，避免被 Wikipedia 擋"""
    resp = requests.get(url, headers=_HEADERS, timeout=30)
    resp.raise_for_status()
    return pd.read_html(resp.text)


def fetch_sp500() -> pd.DataFrame:
    """從 Wikipedia 取得 S&P 500 成分股"""
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    tables = _read_html_with_headers(url)
    df = tables[0]
    df = df.rename(columns={
        "Symbol": "ticker",
        "Security": "name",
        "GICS Sector": "sector",
        "GICS Sub-Industry": "sub_industry",
    })
    # 修正 ticker 格式（Wikipedia 有時用 BRK.B 但 yfinance 用 BRK-B）
    df["ticker"] = df["ticker"].str.replace(".", "-", regex=False)
    return df[["ticker", "name", "sector", "sub_industry"]]


def fetch_nasdaq100() -> pd.DataFrame:
    """從 Wikipedia 取得 Nasdaq 100 成分股"""
    url = "https://en.wikipedia.org/wiki/Nasdaq-100"
    tables = _read_html_with_headers(url)
    # Nasdaq 100 表格通常是第四個（可能因頁面變動需要調整）
    for t in tables:
        cols = [c.lower() for c in t.columns]
        if "ticker" in cols or "symbol" in cols:
            df = t
            break
    else:
        # fallback：找包含 AAPL 的表格
        for t in tables:
            if t.apply(lambda row: row.astype(str).str.contains("AAPL").any(), axis=1).any():
                df = t
                break
        else:
            logger.warning("無法從 Wikipedia 取得 Nasdaq 100，使用空清單")
            return pd.DataFrame(columns=["ticker", "name", "sector", "sub_industry"])

    # 標準化欄位名稱
    col_map = {}
    for c in df.columns:
        cl = str(c).lower()
        if "ticker" in cl or "symbol" in cl:
            col_map[c] = "ticker"
        elif "company" in cl or "security" in cl or "name" in cl:
            col_map[c] = "name"
        elif "sector" in cl or "industry" in cl:
            col_map[c] = "sector"

    df = df.rename(columns=col_map)

    if "ticker" not in df.columns:
        logger.warning("Nasdaq 100 表格欄位不符預期")
        return pd.DataFrame(columns=["ticker", "name", "sector", "sub_industry"])

    if "name" not in df.columns:
        df["name"] = ""
    if "sector" not in df.columns:
        df["sector"] = ""
    if "sub_industry" not in df.columns:
        df["sub_industry"] = ""

    df["ticker"] = df["ticker"].str.replace(".", "-", regex=False)
    return df[["ticker", "name", "sector", "sub_industry"]]


def get_universe(use_cache: bool = True) -> pd.DataFrame:
    """
    取得 S&P 500 + Nasdaq 100 去重後的完整成分股清單。

    Returns: DataFrame with columns [ticker, name, sector, sub_industry]
    """
    # 檢查快取
    if use_cache and os.path.exists(UNIVERSE_CACHE):
        mod_time = datetime.fromtimestamp(os.path.getmtime(UNIVERSE_CACHE))
        days_old = (datetime.now() - mod_time).days
        if days_old < 30:  # 快取 30 天有效
            logger.info(f"📦 使用快取的 universe（{days_old} 天前更新）")
            with open(UNIVERSE_CACHE, "r") as f:
                data = json.load(f)
            df = pd.DataFrame(data)
            # 如果快取是空的，不要使用，重新抓取
            if len(df) > 0 and "ticker" in df.columns:
                return df
            else:
                logger.warning("⚠️ 快取的 universe 為空，重新抓取...")

    logger.info("🔄 從 Wikipedia 取得成分股清單...")

    try:
        sp500 = fetch_sp500()
        logger.info(f"  S&P 500: {len(sp500)} 檔")
    except Exception as e:
        logger.error(f"  S&P 500 取得失敗: {e}")
        sp500 = pd.DataFrame(columns=["ticker", "name", "sector", "sub_industry"])

    try:
        ndx100 = fetch_nasdaq100()
        logger.info(f"  Nasdaq 100: {len(ndx100)} 檔")
    except Exception as e:
        logger.error(f"  Nasdaq 100 取得失敗: {e}")
        ndx100 = pd.DataFrame(columns=["ticker", "name", "sector", "sub_industry"])

    # 合併並去重（以 S&P 500 的資訊為優先）
    combined = pd.concat([sp500, ndx100], ignore_index=True)
    combined = combined.drop_duplicates(subset="ticker", keep="first")
    combined = combined.sort_values("ticker").reset_index(drop=True)

    logger.info(f"✅ 合併後共 {len(combined)} 檔不重複標的")

    # 儲存快取（只在有數據時才存）
    if len(combined) > 0:
        try:
            with open(UNIVERSE_CACHE, "w") as f:
                json.dump(combined.to_dict("records"), f)
            logger.info(f"💾 Universe 已快取")
        except Exception as e:
            logger.warning(f"快取儲存失敗: {e}")
    else:
        logger.error("❌ 合併後清單為空，不儲存快取")
        # 刪除舊的空快取（如果存在）
        if os.path.exists(UNIVERSE_CACHE):
            os.remove(UNIVERSE_CACHE)

    return combined


def get_all_tickers(use_cache: bool = True) -> list:
    """取得所有 ticker 代號的 list"""
    df = get_universe(use_cache)
    if df.empty or "ticker" not in df.columns:
        logger.error("Universe 為空！無法取得 ticker 清單")
        return []
    return df["ticker"].tolist()


def get_sector_map(use_cache: bool = True) -> dict:
    """取得 ticker → sector 的對照 dict"""
    df = get_universe(use_cache)
    if df.empty or "ticker" not in df.columns or "sector" not in df.columns:
        logger.error("Universe 為空！無法建立 sector map")
        return {}
    return dict(zip(df["ticker"], df["sector"]))
