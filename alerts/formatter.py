"""
alerts/formatter.py — 美股版 LINE 訊息格式化（中文化版）
所有標的顯示「代號 中文名」，產業附帶中文簡介。
"""

import pandas as pd
from datetime import datetime
import config

# ── 主要美股中文名稱對照表 ──────────────────────────────────
STOCK_CN_NAMES = {
    # 科技巨頭
    "AAPL": "蘋果", "MSFT": "微軟", "GOOG": "谷歌", "GOOGL": "谷歌",
    "AMZN": "亞馬遜", "META": "Meta", "TSLA": "特斯拉", "NFLX": "網飛",
    # 半導體
    "NVDA": "輝達", "AMD": "超微", "INTC": "英特爾", "AVGO": "博通",
    "QCOM": "高通", "TXN": "德州儀器", "MU": "美光", "MRVL": "邁威爾",
    "LRCX": "科林研發", "AMAT": "應材", "KLAC": "科磊", "ASML": "艾司摩爾",
    "TSM": "台積電ADR", "ARM": "安謀", "SMCI": "超微電腦", "MCHP": "微芯",
    "ON": "安森美", "NXPI": "恩智浦", "ADI": "亞德諾",
    # 軟體/雲端
    "CRM": "Salesforce", "NOW": "ServiceNow", "SNOW": "雪花",
    "PLTR": "Palantir", "PANW": "Palo Alto", "CRWD": "CrowdStrike",
    "FTNT": "Fortinet", "ZS": "Zscaler", "NET": "Cloudflare",
    "DDOG": "Datadog", "MDB": "MongoDB", "SHOP": "Shopify",
    # AI/伺服器
    "DELL": "戴爾", "HPE": "慧與", "IBM": "IBM",
    # 通訊/媒體
    "DIS": "迪士尼", "CMCSA": "康卡斯特", "T": "AT&T", "VZ": "威訊",
    "TMUS": "T-Mobile", "SPOT": "Spotify",
    # 金融
    "JPM": "摩根大通", "BAC": "美銀", "WFC": "富國銀行",
    "GS": "高盛", "MS": "摩根士丹利", "BLK": "貝萊德",
    "V": "Visa", "MA": "萬事達卡", "PYPL": "PayPal", "SQ": "Block",
    "COIN": "Coinbase",
    # 醫療/生技
    "JNJ": "嬌生", "UNH": "聯合健康", "LLY": "禮來",
    "PFE": "輝瑞", "ABBV": "艾伯維", "MRK": "默沙東",
    "AMGN": "安進", "GILD": "吉利德", "MRNA": "莫德納",
    "NVO": "諾和諾德", "VRTX": "Vertex", "REGN": "再生元",
    "ISRG": "直覺手術", "TMO": "賽默飛", "ABT": "亞培",
    "DXCM": "德康醫療",
    # 消費
    "KO": "可口可樂", "PEP": "百事", "PG": "寶潔",
    "COST": "好市多", "WMT": "沃爾瑪", "TGT": "Target",
    "NKE": "耐吉", "SBUX": "星巴克", "MCD": "麥當勞",
    "HD": "家得寶", "LOW": "勞氏", "LULU": "Lululemon",
    # 能源
    "XOM": "埃克森美孚", "CVX": "雪佛龍", "COP": "康菲石油",
    "OXY": "西方石油", "SLB": "斯倫貝謝", "DVN": "德文能源",
    "VLO": "瓦萊羅能源", "PSX": "菲利普斯66", "MPC": "馬拉松石油",
    "APA": "阿帕契", "FANG": "鑽石背能源", "EOG": "EOG資源",
    "HAL": "哈里伯頓", "BKR": "貝克休斯",
    # 工業
    "BA": "波音", "CAT": "卡特彼勒", "DE": "迪爾",
    "GE": "奇異", "HON": "霍尼韋爾", "RTX": "雷神",
    "LMT": "洛克希德馬丁", "NOC": "諾斯洛普格魯曼", "GD": "通用動力",
    "UPS": "UPS", "FDX": "聯邦快遞", "UNP": "聯合太平洋",
    "ETN": "伊頓", "EMR": "艾默生",
    # 電力/公用事業
    "NEE": "NextEra能源", "DUK": "杜克能源", "SO": "南方公司",
    "AES": "AES能源", "VST": "Vistra能源", "CEG": "星座能源",
    # 材料
    "FCX": "自由港麥克莫蘭", "NEM": "紐蒙特", "APD": "空氣化工",
    "ALB": "雅保", "CCJ": "卡梅科",
    # 房地產
    "DLR": "數位不動產", "EQIX": "Equinix", "AMT": "美國電塔",
    "PLD": "普洛斯", "SPG": "西蒙地產",
    # ETF
    "SPY": "標普500ETF", "QQQ": "納指100ETF", "IWM": "羅素2000ETF",
    "XLK": "科技ETF", "SMH": "半導體ETF", "XLE": "能源ETF",
    "XLF": "金融ETF", "XLV": "醫療ETF", "XLI": "工業ETF",
    "XLU": "公用事業ETF", "XLY": "消費ETF", "XLP": "必需消費ETF",
    "XLRE": "房地產ETF", "XLB": "原物料ETF", "XLC": "通訊ETF",
    "IGV": "軟體ETF", "XBI": "生技ETF", "ICLN": "清潔能源ETF",
    # 其他
    "BRK-B": "波克夏", "UBER": "Uber", "ABNB": "Airbnb",
    "RBLX": "Roblox", "RIVN": "Rivian", "LCID": "Lucid",
    "DKNG": "DraftKings", "MSTR": "MicroStrategy",
}

# ── GICS 產業中文名稱與簡介 ────────────────────────────────
SECTOR_INFO = {
    "Technology": ("科技", "軟體、硬體、IT服務"),
    "Information Technology": ("資訊科技", "半導體、軟體、IT服務"),
    "Semiconductors & Semiconductor Equipment": ("半導體", "晶片設計、製造、設備"),
    "Communication Services": ("通訊服務", "社群媒體、串流、電信"),
    "Health Care": ("醫療保健", "製藥、生技、醫療器材"),
    "Financials": ("金融", "銀行、保險、資產管理"),
    "Energy": ("能源", "石油、天然氣、能源服務"),
    "Industrials": ("工業", "航太國防、機械、運輸"),
    "Consumer Discretionary": ("非必需消費", "零售、汽車、休閒"),
    "Consumer Staples": ("必需消費", "食品、飲料、家用品"),
    "Utilities": ("公用事業", "電力、天然氣、水務"),
    "Real Estate": ("房地產", "REIT、資料中心、商業地產"),
    "Materials": ("原物料", "化工、金屬、礦業"),
}


def _get_cn_name(ticker: str) -> str:
    """取得中文名稱，沒有則回傳空字串"""
    return STOCK_CN_NAMES.get(ticker, "")


def _get_stock_label(r) -> str:
    """組合 'TICKER 中文名' 標籤"""
    ticker = r.get("ticker", "")
    cn = _get_cn_name(ticker)
    if cn:
        return f"{ticker} {cn}"
    return ticker


def _get_sector_cn(sector: str) -> tuple:
    """回傳 (中文名, 簡介)"""
    return SECTOR_INFO.get(sector, (sector, ""))


def _stars_str(n: int) -> str:
    return "★" * n + "☆" * (5 - n)


def format_daily_report(
    scored_df: pd.DataFrame,
    transitions: dict,
    theme_info: dict = None,
) -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    lines = []

    lines.append("═" * 22)
    lines.append("📡 美股趨勢雷達日報")
    lines.append(f"📅 {today}")
    lines.append("═" * 22)

    if scored_df.empty:
        lines.append("\n⚠️ 今日無評分數據")
        return "\n".join(lines)

    # ── 新進觀察名單 ──
    new_s1 = transitions.get("new_stage1", [])
    if new_s1:
        lines.append(f"\n🔥 新進觀察名單 ({len(new_s1)} 檔)")
        for ticker in new_s1[:8]:
            row = scored_df[scored_df["ticker"] == ticker]
            if row.empty:
                continue
            r = row.iloc[0]
            label = _get_stock_label(r)
            sector = r.get("sector", "")
            sector_cn, _ = _get_sector_cn(sector)

            lines.append(
                f"  {label} {_stars_str(r['stars'])} {r['total_score']:.0f}分"
            )
            lines.append(f"    📂 {sector_cn} | {r['details'].get('volume', '')}")

    # ── Stage 2 加速 ──
    stage2 = scored_df[scored_df["stage"] == 2].head(10) if "stage" in scored_df.columns else pd.DataFrame()
    if not stage2.empty:
        lines.append(f"\n🚀 趨勢加速中 ({len(stage2)} 檔)")
        for _, r in stage2.iterrows():
            label = _get_stock_label(r)
            days = r.get("days_above_70", 0)
            sector_cn, _ = _get_sector_cn(r.get("sector", ""))
            lines.append(
                f"  {label} {_stars_str(r['stars'])} {r['total_score']:.0f}分"
                f" | {sector_cn} | 第{days}天"
            )

    # ── 新確認趨勢 ──
    new_s2 = transitions.get("new_stage2", [])
    if new_s2:
        lines.append(f"\n⭐ 新確認趨勢 (→Stage 2)")
        for ticker in new_s2[:5]:
            row = scored_df[scored_df["ticker"] == ticker]
            if row.empty:
                continue
            r = row.iloc[0]
            label = _get_stock_label(r)
            sector_cn, _ = _get_sector_cn(r.get("sector", ""))
            lines.append(f"  {label} | {sector_cn}")

    # ── 趨勢疲軟 ──
    decay_s3 = transitions.get("decay_stage3", [])
    if decay_s3:
        lines.append(f"\n⚠️ 趨勢疲軟 ({len(decay_s3)} 檔)")
        for ticker in decay_s3[:5]:
            row = scored_df[scored_df["ticker"] == ticker]
            if row.empty:
                continue
            r = row.iloc[0]
            label = _get_stock_label(r)
            lines.append(
                f"  {label} {r['total_score']:.0f}分"
                f" | {r['details'].get('rs', '')}"
            )

    # ── 升溫主題（含中文簡介）──
    if theme_info and theme_info.get("active_themes"):
        active = [t for t in theme_info["active_themes"] if t.get("status") == "rising"]
        if active:
            lines.append(f"\n🌐 升溫主題 ({len(active)} 個)")
            for t in active[:5]:
                theme_name = t.get("theme", t.get("keyword", "?"))
                acc = t.get("acceleration", 0)
                tickers = t.get("tickers", [])
                reasoning = t.get("reasoning", "")

                lines.append(f"\n  🔺 {theme_name}（熱度 {acc:.1f}x）")
                if reasoning:
                    lines.append(f"    💡 {reasoning[:40]}")

                # 關聯個股（附中文名）
                if tickers:
                    stock_labels = []
                    for tk in tickers[:6]:
                        cn = _get_cn_name(tk)
                        stock_labels.append(f"{tk}{cn}" if cn else tk)
                    lines.append(f"    → {', '.join(stock_labels)}")

    # ── 產業強度（含中文名和簡介）──
    if "sector" in scored_df.columns:
        sector_strength = (
            scored_df[scored_df["total_score"] >= 55]
            .groupby("sector")
            .size()
            .sort_values(ascending=False)
            .head(5)
        )
        if not sector_strength.empty:
            lines.append("\n🏭 產業強度 (★★★以上)")
            for sector, count in sector_strength.items():
                total_in = (scored_df["sector"] == sector).sum()
                pct = count / total_in * 100 if total_in > 0 else 0
                sector_cn, sector_desc = _get_sector_cn(sector)
                line = f"  {sector_cn}: {count}檔 ({pct:.0f}%)"
                if sector_desc:
                    line += f"\n    💡 {sector_desc}"
                lines.append(line)

    # ── 統計 ──
    watchlist_count = (scored_df["stars"] >= 4).sum()
    stage1_count = (scored_df["stage"] == 1).sum() if "stage" in scored_df.columns else 0
    stage2_count = (scored_df["stage"] == 2).sum() if "stage" in scored_df.columns else 0

    lines.append(f"\n📊 觀察名單: {watchlist_count} 檔 (★★★★以上)")
    lines.append(f"   Stage 1 覺醒: {stage1_count} | Stage 2 加速: {stage2_count}")

    # ── Top 5（完整中文資訊）──
    top5 = scored_df.head(5)
    if not top5.empty:
        lines.append("\n🏆 今日 Top 5")
        for _, r in top5.iterrows():
            label = _get_stock_label(r)
            sector_cn, _ = _get_sector_cn(r.get("sector", ""))
            vol_detail = r.get("details", {}).get("volume", "") if isinstance(r.get("details"), dict) else ""

            lines.append(
                f"  {label} {r['total_score']:.1f}分 {_stars_str(r['stars'])}"
            )
            info = f"    {sector_cn}"
            if vol_detail:
                info += f" | {vol_detail}"
            lines.append(info)

    lines.append(f"\n{'═' * 22}")
    lines.append("📡 Trend Radar v1.0")

    return "\n".join(lines)


def format_short_alert(scored_df: pd.DataFrame, transitions: dict) -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    lines = [f"📡 美股趨勢雷達 {today}", ""]

    new_s1 = transitions.get("new_stage1", [])
    new_s2 = transitions.get("new_stage2", [])
    decay = transitions.get("decay_stage3", [])

    if not new_s1 and not new_s2 and not decay:
        watchlist = (scored_df["stars"] >= 4).sum() if not scored_df.empty else 0
        lines.append(f"📊 無重大變化 | 觀察名單(★★★★+): {watchlist}檔")

        if not scored_df.empty:
            top3 = scored_df.head(3)
            lines.append("\n🏆 Top 3:")
            for _, r in top3.iterrows():
                label = _get_stock_label(r)
                sector_cn, _ = _get_sector_cn(r.get("sector", ""))
                lines.append(f"  {label} {r['total_score']:.0f}分 | {sector_cn}")
    else:
        if new_s1:
            lines.append(f"🔥 新進觀察 ({len(new_s1)} 檔):")
            for t in new_s1[:5]:
                cn = _get_cn_name(t)
                lines.append(f"  {t} {cn}" if cn else f"  {t}")
        if new_s2:
            lines.append(f"⭐ 趨勢確認:")
            for t in new_s2[:5]:
                cn = _get_cn_name(t)
                lines.append(f"  {t} {cn}" if cn else f"  {t}")
        if decay:
            lines.append(f"⚠️ 趨勢疲軟:")
            for t in decay[:5]:
                cn = _get_cn_name(t)
                lines.append(f"  {t} {cn}" if cn else f"  {t}")

    return "\n".join(lines)
