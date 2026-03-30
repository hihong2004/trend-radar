"""
scoring/sector_momentum.py — 維度 5：產業族群共振
衡量同 GICS Sector 中其他股票是否也在走強。
"""

import pandas as pd
import numpy as np


def score_sector_momentum(
    ticker: str,
    sector: str,
    all_rs_scores: pd.Series,
    sector_map: dict,
    sector_etf_rs: dict = None,
) -> dict:
    """
    評估產業族群共振強度。

    Parameters
    ----------
    ticker : 當前股票代號
    sector : 該股的 GICS Sector
    all_rs_scores : Series indexed by ticker, values = raw RS
    sector_map : dict of ticker -> sector
    sector_etf_rs : dict of sector -> ETF RS percentile (optional)

    Returns
    -------
    dict: {"score": float, "sector_strong_pct": float, "details": str}
    """
    result = {
        "score": 0,
        "sector_strong_pct": 0,
        "sector_etf_rs_pct": 0,
        "sector_peers_count": 0,
        "details": "",
    }

    if not sector or sector == "":
        result["details"] = "無 Sector 資訊"
        result["score"] = 30  # 中性分
        return result

    # 找出同 sector 的所有 ticker
    peers = [t for t, s in sector_map.items() if s == sector and t != ticker]

    if len(peers) < 3:
        result["details"] = f"同業太少（{len(peers)} 檔）"
        result["score"] = 30
        return result

    # 計算同 sector 中 RS > 70th percentile 的比例
    if len(all_rs_scores) > 10:
        rs_70th = all_rs_scores.quantile(0.70)
        peer_rs = all_rs_scores.reindex(peers).dropna()

        if len(peer_rs) > 0:
            strong_pct = (peer_rs > rs_70th).mean() * 100
        else:
            strong_pct = 0
    else:
        strong_pct = 0

    result["sector_strong_pct"] = round(strong_pct, 1)
    result["sector_peers_count"] = len(peers)

    # 產業 ETF 的 RS
    etf_rs_pct = 0
    if sector_etf_rs and sector in sector_etf_rs:
        etf_rs_pct = sector_etf_rs[sector]
        result["sector_etf_rs_pct"] = round(etf_rs_pct, 1)

    # 評分
    score = 0
    if strong_pct > 50 and etf_rs_pct > 80:
        score = 95
    elif strong_pct > 50:
        score = 85
    elif strong_pct > 30 and etf_rs_pct > 60:
        score = 75
    elif strong_pct > 30:
        score = 65
    elif strong_pct > 15:
        score = 50
    elif strong_pct > 5:
        score = 35
    else:
        score = 20

    result["score"] = score
    result["details"] = (
        f"{sector}: {strong_pct:.0f}%走強 "
        f"({len(peers)}檔同業)"
    )
    return result


def compute_sector_etf_rs(
    sector_etf_ohlcv: pd.DataFrame,
    benchmark_close: pd.Series,
) -> dict:
    """
    計算所有產業 ETF 的 RS 百分位排名。
    Returns: dict of ETF_ticker -> RS percentile
    """
    from scoring.relative_strength import compute_returns

    etf_rs = {}
    for ticker, group in sector_etf_ohlcv.groupby("ticker"):
        close = group.sort_values("date")["close"]
        if len(close) < 61:
            continue

        stock_ret_60 = compute_returns(close, 60)
        bench_ret_60 = compute_returns(benchmark_close, 60)

        if not np.isnan(stock_ret_60) and not np.isnan(bench_ret_60):
            etf_rs[ticker] = stock_ret_60 - bench_ret_60

    if not etf_rs:
        return {}

    # 轉換為百分位
    rs_series = pd.Series(etf_rs)
    percentiles = {}
    for ticker, val in etf_rs.items():
        pct = (rs_series < val).mean() * 100
        percentiles[ticker] = pct

    return percentiles


def map_sector_to_etf_rs(sector: str, etf_percentiles: dict) -> float:
    """將 GICS Sector 映射到對應 ETF 的 RS 百分位"""
    import config
    etf_ticker = config.SECTOR_ETFS.get(sector)
    if etf_ticker and etf_ticker in etf_percentiles:
        return etf_percentiles[etf_ticker]
    return 50  # default neutral
