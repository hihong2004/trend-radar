"""
data_pipeline.py — 批量數據下載與快取
負責下載 550+ 檔個股的 OHLCV 日線數據，支援增量更新。
"""

import time
import logging
import pandas as pd
import numpy as np
import os
from datetime import datetime, timedelta

import yfinance as yf
import config

logger = logging.getLogger(__name__)

OHLCV_CACHE = os.path.join(config.CACHE_DIR, "ohlcv_all.parquet")
BENCHMARK_CACHE = os.path.join(config.CACHE_DIR, "benchmark.parquet")
SECTOR_ETF_CACHE = os.path.join(config.CACHE_DIR, "sector_etfs.parquet")


def _download_batch(tickers: list, start: str, end: str = None) -> pd.DataFrame:
    """
    下載一批 ticker 的收盤數據。
    回傳 long-format DataFrame: [date, ticker, open, high, low, close, volume]
    """
    try:
        data = yf.download(
            tickers,
            start=start,
            end=end,
            auto_adjust=True,
            progress=False,
            timeout=60,
            threads=True,
        )
    except Exception as e:
        logger.error(f"yfinance 下載失敗: {e}")
        return pd.DataFrame()

    if data.empty:
        return pd.DataFrame()

    # yfinance 回傳 MultiIndex columns: (Price, Ticker)
    # 轉成 long format
    frames = []
    price_cols = ["Open", "High", "Low", "Close", "Volume"]

    if isinstance(data.columns, pd.MultiIndex):
        available_tickers = data.columns.get_level_values(1).unique()
        for ticker in available_tickers:
            try:
                df_t = data.xs(ticker, level=1, axis=1).copy()
                df_t = df_t[[c for c in price_cols if c in df_t.columns]]
                df_t.columns = [c.lower() for c in df_t.columns]
                df_t["ticker"] = ticker
                df_t.index.name = "date"
                df_t = df_t.reset_index()
                frames.append(df_t)
            except Exception:
                continue
    else:
        # 單一 ticker 的情況
        data.columns = [c.lower() if isinstance(c, str) else c for c in data.columns]
        if len(tickers) == 1:
            data["ticker"] = tickers[0]
        data.index.name = "date"
        data = data.reset_index()
        frames.append(data)

    if not frames:
        return pd.DataFrame()

    result = pd.concat(frames, ignore_index=True)
    result["date"] = pd.to_datetime(result["date"])
    return result


def download_all_ohlcv(tickers: list, full_refresh: bool = False) -> pd.DataFrame:
    """
    下載所有 ticker 的 OHLCV 數據。
    支援增量更新：如果快取存在且非 full_refresh，只下載最近幾天。
    """
    # 判斷是否需要完整下載
    if not full_refresh and os.path.exists(OHLCV_CACHE):
        logger.info("📦 讀取快取數據...")
        cached = pd.read_parquet(OHLCV_CACHE)
        cached["date"] = pd.to_datetime(cached["date"])

        last_date = cached["date"].max()
        days_behind = (datetime.now() - last_date).days

        if days_behind <= 1:
            logger.info(f"  快取已是最新（{last_date.date()}）")
            return cached

        # 增量更新
        start_date = (last_date - timedelta(days=config.INCREMENTAL_DAYS)).strftime("%Y-%m-%d")
        logger.info(f"🔄 增量更新：從 {start_date} 開始")

        new_data = _batch_download(tickers, start_date)

        if not new_data.empty:
            # 合併：移除舊的重疊日期，用新數據替換
            cutoff = pd.to_datetime(start_date)
            old_data = cached[cached["date"] < cutoff]
            combined = pd.concat([old_data, new_data], ignore_index=True)
            combined = combined.drop_duplicates(subset=["date", "ticker"], keep="last")
            combined = combined.sort_values(["ticker", "date"]).reset_index(drop=True)
        else:
            combined = cached

        _save_cache(combined, OHLCV_CACHE)
        return combined

    # 完整下載
    years = config.DATA_HISTORY_YEARS
    start_date = (datetime.now() - timedelta(days=years * 365)).strftime("%Y-%m-%d")
    logger.info(f"🔄 完整下載：{len(tickers)} 檔，從 {start_date} 開始")

    result = _batch_download(tickers, start_date)
    _save_cache(result, OHLCV_CACHE)
    return result


def _batch_download(tickers: list, start_date: str) -> pd.DataFrame:
    """分批下載，避免 Yahoo Finance 限流"""
    batch_size = config.DATA_BATCH_SIZE
    all_frames = []
    total_batches = (len(tickers) + batch_size - 1) // batch_size

    for i in range(0, len(tickers), batch_size):
        batch = tickers[i: i + batch_size]
        batch_num = i // batch_size + 1
        logger.info(f"  批次 {batch_num}/{total_batches}: {len(batch)} 檔")

        try:
            df = _download_batch(batch, start=start_date)
            if not df.empty:
                all_frames.append(df)
                logger.info(f"    ✅ 取得 {df['ticker'].nunique()} 檔數據")
            else:
                logger.warning(f"    ⚠️ 空數據")
        except Exception as e:
            logger.error(f"    ❌ 批次失敗: {e}")

        if batch_num < total_batches:
            time.sleep(config.DATA_BATCH_DELAY)

    if not all_frames:
        return pd.DataFrame()

    result = pd.concat(all_frames, ignore_index=True)
    result = result.drop_duplicates(subset=["date", "ticker"], keep="last")
    logger.info(f"✅ 共下載 {result['ticker'].nunique()} 檔，{len(result)} 筆資料")
    return result


def download_benchmark(full_refresh: bool = False) -> pd.DataFrame:
    """下載 SPY 基準數據"""
    if not full_refresh and os.path.exists(BENCHMARK_CACHE):
        cached = pd.read_parquet(BENCHMARK_CACHE)
        last_date = pd.to_datetime(cached["date"]).max()
        if (datetime.now() - last_date).days <= 1:
            return cached

    years = config.DATA_HISTORY_YEARS
    start = (datetime.now() - timedelta(days=years * 365)).strftime("%Y-%m-%d")
    df = _download_batch([config.BENCHMARK], start)
    _save_cache(df, BENCHMARK_CACHE)
    return df


def download_sector_etfs(full_refresh: bool = False) -> pd.DataFrame:
    """下載所有產業 ETF 數據"""
    if not full_refresh and os.path.exists(SECTOR_ETF_CACHE):
        cached = pd.read_parquet(SECTOR_ETF_CACHE)
        last_date = pd.to_datetime(cached["date"]).max()
        if (datetime.now() - last_date).days <= 1:
            return cached

    etf_tickers = list(config.ALL_SECTOR_ETFS.values())
    years = config.DATA_HISTORY_YEARS
    start = (datetime.now() - timedelta(days=years * 365)).strftime("%Y-%m-%d")
    df = _batch_download(etf_tickers, start)
    _save_cache(df, SECTOR_ETF_CACHE)
    return df


def _save_cache(df: pd.DataFrame, path: str):
    """儲存 parquet 快取"""
    if df.empty:
        return
    try:
        df.to_parquet(path, index=False)
        logger.info(f"💾 已快取至 {os.path.basename(path)}")
    except Exception as e:
        logger.warning(f"快取儲存失敗: {e}")


def get_ticker_df(ohlcv: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """從 long-format OHLCV 中提取單一 ticker 的 DataFrame"""
    df = ohlcv[ohlcv["ticker"] == ticker].copy()
    df = df.sort_values("date").reset_index(drop=True)
    return df


def load_all_data(full_refresh: bool = False) -> dict:
    """
    主入口：載入所有需要的數據。

    Returns: dict with keys:
      - "ohlcv": long-format DataFrame of all stocks
      - "benchmark": SPY DataFrame
      - "sector_etfs": sector ETF DataFrame
      - "tickers": list of tickers
      - "sector_map": dict of ticker -> sector
    """
    from universe import get_all_tickers, get_sector_map

    tickers = get_all_tickers()
    sector_map = get_sector_map()

    logger.info(f"📊 Universe: {len(tickers)} 檔標的")

    benchmark = download_benchmark(full_refresh)
    logger.info(f"📊 Benchmark (SPY): {len(benchmark)} 筆")

    sector_etfs = download_sector_etfs(full_refresh)
    logger.info(f"📊 Sector ETFs: {sector_etfs['ticker'].nunique() if not sector_etfs.empty else 0} 檔")

    ohlcv = download_all_ohlcv(tickers, full_refresh)
    logger.info(f"📊 OHLCV: {ohlcv['ticker'].nunique() if not ohlcv.empty else 0} 檔")

    return {
        "ohlcv": ohlcv,
        "benchmark": benchmark,
        "sector_etfs": sector_etfs,
        "tickers": tickers,
        "sector_map": sector_map,
    }
