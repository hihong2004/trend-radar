"""
scoring/composite.py — 總分合成 + Stage 判定
將七個維度的分數加權合成，判定趨勢階段，產出最終排名。
"""

import pandas as pd
import numpy as np
import logging
import os
import json
from datetime import datetime

import config
from data_pipeline import get_ticker_df
from scoring.relative_strength import (
    score_relative_strength,
    compute_all_raw_rs,
)
from scoring.price_structure import score_price_structure
from scoring.volume_analysis import score_volume
from scoring.volatility import score_volatility
from scoring.sector_momentum import (
    score_sector_momentum,
    compute_sector_etf_rs,
    map_sector_to_etf_rs,
)
from scoring.trend_consistency import score_trend_consistency
from scoring.theme_momentum import score_theme_momentum

logger = logging.getLogger(__name__)

STAGE_HISTORY_PATH = os.path.join(config.CACHE_DIR, "stage_history.json")


def score_single_ticker(
    ticker: str,
    ohlcv: pd.DataFrame,
    benchmark_close: pd.Series,
    all_rs_scores: pd.Series,
    sector_map: dict,
    sector_etf_rs: dict,
) -> dict:
    """
    對單一股票計算七維評分與總分。
    """
    df = get_ticker_df(ohlcv, ticker)

    if df.empty or len(df) < 60:
        return None

    close = df.set_index("date")["close"]
    volume = df.set_index("date")["volume"]
    sector = sector_map.get(ticker, "")

    # 對齊 benchmark
    bench_aligned = benchmark_close.reindex(close.index).ffill()

    # ── 七維評分 ──
    d1 = score_relative_strength(close, bench_aligned, all_rs_scores)
    d2 = score_price_structure(close)
    d3 = score_volume(close, volume)
    d4 = score_volatility(close)
    d5 = score_sector_momentum(
        ticker, sector, all_rs_scores, sector_map,
        sector_etf_rs=sector_etf_rs,
    )
    d6 = score_trend_consistency(close)
    d7 = score_theme_momentum(ticker)

    # ── 加權總分 ──
    weights = config.SCORING_WEIGHTS
    total = (
        d1["score"] * weights["relative_strength"]
        + d2["score"] * weights["price_structure"]
        + d3["score"] * weights["volume_analysis"]
        + d4["score"] * weights["volatility"]
        + d5["score"] * weights["sector_momentum"]
        + d6["score"] * weights["trend_consistency"]
        + d7["score"] * weights["theme_momentum"]
    )
    total = round(min(total, 100), 1)

    # ── 星級 ──
    stars = 1
    for s, threshold in sorted(config.RATING_THRESHOLDS.items(), reverse=True):
        if total >= threshold:
            stars = s
            break

    return {
        "ticker": ticker,
        "sector": sector,
        "total_score": total,
        "stars": stars,
        "price": round(float(close.iloc[-1]), 2),
        "dimensions": {
            "relative_strength": d1["score"],
            "price_structure": d2["score"],
            "volume_analysis": d3["score"],
            "volatility": d4["score"],
            "sector_momentum": d5["score"],
            "trend_consistency": d6["score"],
            "theme_momentum": d7["score"],
        },
        "details": {
            "rs": d1["details"],
            "price": d2["details"],
            "volume": d3["details"],
            "volatility": d4["details"],
            "sector": d5["details"],
            "consistency": d6["details"],
            "theme": d7["details"],
        },
        "themes": d7.get("themes", []),
    }


def score_all_tickers(data: dict) -> pd.DataFrame:
    """
    對所有 ticker 進行評分。

    Parameters
    ----------
    data : dict from data_pipeline.load_all_data()

    Returns
    -------
    DataFrame with scoring results, sorted by total_score desc
    """
    ohlcv = data["ohlcv"]
    benchmark = data["benchmark"]
    sector_etfs_df = data["sector_etfs"]
    tickers = data["tickers"]
    sector_map = data["sector_map"]

    if ohlcv.empty:
        logger.error("OHLCV 數據為空")
        return pd.DataFrame()

    # 準備 benchmark close series
    bench_df = benchmark[benchmark["ticker"] == config.BENCHMARK].sort_values("date")
    benchmark_close = bench_df.set_index("date")["close"]

    # 計算全體 RS（用於排名）
    logger.info("📊 計算全體相對強度...")
    all_rs_scores = compute_all_raw_rs(ohlcv, benchmark_close)
    logger.info(f"  {len(all_rs_scores)} 檔有 RS 數據")

    # 計算產業 ETF RS
    logger.info("📊 計算產業 ETF 相對強度...")
    etf_rs_percentiles = compute_sector_etf_rs(sector_etfs_df, benchmark_close)

    # 建立 sector → ETF RS 的映射
    sector_etf_rs = {}
    for sector in set(sector_map.values()):
        sector_etf_rs[sector] = map_sector_to_etf_rs(sector, etf_rs_percentiles)

    # 對每檔股票評分
    logger.info(f"📊 開始評分 {len(tickers)} 檔股票...")
    results = []
    scored = 0
    skipped = 0

    for i, ticker in enumerate(tickers):
        try:
            r = score_single_ticker(
                ticker, ohlcv, benchmark_close,
                all_rs_scores, sector_map, sector_etf_rs,
            )
            if r:
                results.append(r)
                scored += 1
            else:
                skipped += 1
        except Exception as e:
            logger.debug(f"  {ticker} 評分失敗: {e}")
            skipped += 1

        if (i + 1) % 100 == 0:
            logger.info(f"  進度: {i+1}/{len(tickers)}")

    logger.info(f"✅ 評分完成: {scored} 成功, {skipped} 跳過")

    if not results:
        return pd.DataFrame()

    df = pd.DataFrame(results)
    df = df.sort_values("total_score", ascending=False).reset_index(drop=True)

    return df


def determine_stages(scores_df: pd.DataFrame) -> pd.DataFrame:
    """
    根據評分結果和歷史記錄，判定每檔股票的趨勢階段。
    """
    if scores_df.empty:
        return scores_df

    params = config.STAGE_PARAMS

    # 載入歷史 stage 記錄
    history = _load_stage_history()

    stages = []
    today = datetime.now().strftime("%Y-%m-%d")

    for _, row in scores_df.iterrows():
        ticker = row["ticker"]
        total = row["total_score"]
        sector_score = row["dimensions"]["sector_momentum"]

        prev = history.get(ticker, {})
        prev_stage = prev.get("stage", 0)
        prev_high = prev.get("high_score", 0)
        days_above_70 = prev.get("days_above_70", 0)
        first_seen = prev.get("first_seen", today)

        # 更新 high score
        high_score = max(prev_high, total)

        # 更新 days_above_70
        if total >= params["acceleration_threshold"]:
            days_above_70 += 1
        else:
            days_above_70 = 0

        # Stage 判定
        if total < params["awakening_threshold"]:
            stage = 0
        elif (
            total >= params["acceleration_threshold"]
            and days_above_70 >= params["acceleration_hold_days"]
            and sector_score >= params["sector_confirm_threshold"]
        ):
            stage = 2
        elif total >= params["awakening_threshold"]:
            stage = 1
        else:
            stage = 0

        # Stage 3 衰退判定
        if prev_stage == 2:
            score_drop = high_score - total
            if score_drop > params["decay_drop_points"]:
                stage = 3
            rs_score = row["dimensions"]["relative_strength"]
            if rs_score < params["rs_decay_percentile"]:
                stage = 3

        # 偵測 stage 變化
        stage_changed = (stage != prev_stage)
        transition = ""
        if stage_changed:
            transition = f"{prev_stage}→{stage}"

        stages.append({
            "stage": stage,
            "stage_changed": stage_changed,
            "transition": transition,
            "days_above_70": days_above_70,
            "high_score": high_score,
            "first_seen": first_seen if total >= params["awakening_threshold"] else "",
        })

        # 更新歷史
        history[ticker] = {
            "stage": stage,
            "high_score": high_score,
            "days_above_70": days_above_70,
            "first_seen": first_seen if total >= params["awakening_threshold"] else "",
            "last_updated": today,
        }

    # 儲存歷史
    _save_stage_history(history)

    stage_df = pd.DataFrame(stages)
    result = pd.concat([scores_df.reset_index(drop=True), stage_df], axis=1)

    return result


def get_watchlist(scored_df: pd.DataFrame, min_stars: int = 3) -> pd.DataFrame:
    """取得觀察名單（預設 ★★★ 以上）"""
    if scored_df.empty:
        return scored_df
    return scored_df[scored_df["stars"] >= min_stars].copy()


def get_stage_transitions(scored_df: pd.DataFrame) -> dict:
    """取得今日的 Stage 變化摘要"""
    if scored_df.empty or "stage_changed" not in scored_df.columns:
        return {"new_stage1": [], "new_stage2": [], "decay_stage3": []}

    changed = scored_df[scored_df["stage_changed"] == True]

    return {
        "new_stage1": changed[changed["transition"].str.contains("→1")]["ticker"].tolist(),
        "new_stage2": changed[changed["transition"].str.contains("→2")]["ticker"].tolist(),
        "decay_stage3": changed[changed["transition"].str.contains("→3")]["ticker"].tolist(),
    }


def save_daily_snapshot(scored_df: pd.DataFrame):
    """儲存每日評分快照"""
    if scored_df.empty:
        return

    today = datetime.now().strftime("%Y-%m-%d")
    path = os.path.join(config.SCORES_DIR, f"{today}.parquet")

    # 只保存關鍵欄位
    cols = ["ticker", "sector", "total_score", "stars", "stage", "price"]
    save_df = scored_df[[c for c in cols if c in scored_df.columns]].copy()

    try:
        save_df.to_parquet(path, index=False)
        logger.info(f"💾 每日快照已儲存: {path}")
    except Exception as e:
        logger.warning(f"快照儲存失敗: {e}")


def _load_stage_history() -> dict:
    """載入 Stage 歷史記錄"""
    if os.path.exists(STAGE_HISTORY_PATH):
        try:
            with open(STAGE_HISTORY_PATH, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_stage_history(history: dict):
    """儲存 Stage 歷史記錄"""
    try:
        with open(STAGE_HISTORY_PATH, "w") as f:
            json.dump(history, f)
    except Exception as e:
        logger.warning(f"Stage 歷史儲存失敗: {e}")
