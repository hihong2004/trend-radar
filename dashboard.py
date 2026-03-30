"""
dashboard.py — Streamlit 趨勢雷達儀表板
獨立於 daily_scan.py，透過 `streamlit run dashboard.py` 啟動。

5 個分頁：
  Tab 1: 趨勢雷達（觀察名單表格）
  Tab 2: 產業熱力圖
  Tab 3: 主題追蹤
  Tab 4: 個股詳情
  Tab 5: 系統表現追蹤
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
import logging
import sys
import json
import os

logging.basicConfig(level=logging.INFO, stream=sys.stdout)

# ── 頁面設定 ──
st.set_page_config(
    page_title="Trend Radar",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── 深色模式 CSS ──
st.markdown("""
<style>
    .stApp { background-color: #0E1117; }
    .big-badge {
        font-size: 1.8rem; font-weight: bold; padding: 15px;
        border-radius: 10px; text-align: center; margin: 5px 0;
    }
    .section-header {
        font-size: 1.2rem; font-weight: bold; color: #E0E0E0;
        border-bottom: 2px solid #2D3250; padding-bottom: 6px;
        margin: 15px 0 8px 0;
    }
</style>
""", unsafe_allow_html=True)


# ── 數據載入 ──
@st.cache_data(ttl=3600, show_spinner="載入數據中...")
def load_data():
    from data_pipeline import load_all_data
    return load_all_data(full_refresh=False)


@st.cache_data(ttl=3600, show_spinner="計算評分中...")
def compute_scores(_data):
    from scoring.composite import score_all_tickers, determine_stages
    scored = score_all_tickers(_data)
    if not scored.empty:
        scored = determine_stages(scored)
    return scored


def load_theme_groups():
    import config
    path = os.path.join(config.BASE_DIR, "themes", "theme_groups.json")
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {"active_themes": [], "cooling_themes": []}


# ── 圖表工具 ──
def make_radar_chart(dimensions: dict, title: str = "") -> go.Figure:
    """七維雷達圖"""
    labels = {
        "relative_strength": "相對強度",
        "price_structure": "價格結構",
        "volume_analysis": "成交量",
        "volatility": "波動率",
        "sector_momentum": "族群共振",
        "trend_consistency": "趨勢持續",
        "theme_momentum": "主題熱度",
    }
    cats = list(labels.values())
    vals = [dimensions.get(k, 0) for k in labels.keys()]
    vals.append(vals[0])  # close the polygon
    cats.append(cats[0])

    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=vals, theta=cats, fill="toself",
        fillcolor="rgba(0, 212, 170, 0.2)",
        line=dict(color="#00D4AA", width=2),
        name=title,
    ))
    fig.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0, 100], tickfont=dict(size=9, color="#666")),
            bgcolor="rgba(0,0,0,0)",
            angularaxis=dict(tickfont=dict(size=10, color="#AAA")),
        ),
        showlegend=False,
        height=300,
        margin=dict(l=50, r=50, t=30, b=30),
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color="white"),
    )
    return fig


def make_score_bars(dimensions: dict) -> go.Figure:
    """水平條狀圖顯示七維分數"""
    labels = {
        "relative_strength": "RS 相對強度",
        "price_structure": "價格結構",
        "volume_analysis": "成交量",
        "volatility": "波動率突破",
        "sector_momentum": "族群共振",
        "trend_consistency": "趨勢持續",
        "theme_momentum": "主題熱度",
    }
    names = list(labels.values())
    vals = [dimensions.get(k, 0) for k in labels.keys()]
    colors = ["#FF6B6B" if v < 40 else "#FFD93D" if v < 70 else "#00D4AA" for v in vals]

    fig = go.Figure(go.Bar(
        x=vals, y=names, orientation="h",
        marker_color=colors,
        text=[f"{v:.0f}" for v in vals],
        textposition="auto",
        textfont=dict(color="white"),
    ))
    fig.update_layout(
        height=250,
        margin=dict(l=100, r=20, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(14,17,23,1)",
        font=dict(color="#AAA"),
        xaxis=dict(range=[0, 100], gridcolor="#1E2130"),
        yaxis=dict(gridcolor="#1E2130"),
    )
    return fig


def make_price_chart(ohlcv: pd.DataFrame, ticker: str, days: int = 252) -> go.Figure:
    """K 線圖 + 均線 + 成交量"""
    from data_pipeline import get_ticker_df
    df = get_ticker_df(ohlcv, ticker)
    if df.empty:
        return go.Figure()

    df = df.tail(days)
    df["ma50"] = df["close"].rolling(50).mean()
    df["ma200"] = df["close"].rolling(200).mean()

    fig = go.Figure()

    # 收盤價線
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["close"], mode="lines",
        name="Close", line=dict(color="#00D4AA", width=1.5),
    ))
    # 50MA
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["ma50"], mode="lines",
        name="50MA", line=dict(color="#FFD93D", width=1, dash="dash"),
    ))
    # 200MA
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["ma200"], mode="lines",
        name="200MA", line=dict(color="#FF6B6B", width=1, dash="dash"),
    ))

    fig.update_layout(
        height=350,
        margin=dict(l=50, r=20, t=30, b=30),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(14,17,23,1)",
        font=dict(color="#AAA"),
        xaxis=dict(gridcolor="#1E2130"),
        yaxis=dict(gridcolor="#1E2130", title="Price"),
        legend=dict(orientation="h", y=1.1),
    )
    return fig


# ═══════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════
def main():
    # ── 側邊欄 ──
    with st.sidebar:
        st.title("📡 Trend Radar")

        if st.button("🔄 重新載入", type="primary", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

        st.markdown("---")
        min_stars = st.slider("最低星級", 1, 5, 3)
        stage_filter = st.multiselect(
            "Stage 篩選", [0, 1, 2, 3],
            default=[1, 2],
            format_func=lambda x: {0: "💤 沉睡", 1: "🌅 覺醒", 2: "🚀 加速", 3: "⚠️ 衰退"}[x],
        )

        st.markdown("---")
        st.markdown("### 📖 評分說明")
        st.markdown("""
        **★★★★★** 85+ 強烈趨勢
        **★★★★☆** 70-84 趨勢形成中
        **★★★☆☆** 55-69 初步跡象
        """)

    # ── 載入數據 ──
    try:
        data = load_data()
        scored_df = compute_scores(data)
    except Exception as e:
        st.error(f"數據載入失敗: {e}")
        st.info("請確認環境變數已正確設定。")
        return

    if scored_df.empty:
        st.warning("評分結果為空，可能數據尚未下載完成。")
        return

    theme_groups = load_theme_groups()

    # ── 篩選 ──
    filtered = scored_df[scored_df["stars"] >= min_stars]
    if stage_filter and "stage" in filtered.columns:
        filtered = filtered[filtered["stage"].isin(stage_filter)]

    # ═══ 分頁 ═══
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📡 趨勢雷達", "🏭 產業熱力圖", "🌐 主題追蹤",
        "📊 個股詳情", "📈 系統表現",
    ])

    # ════════════════════════════════════
    # Tab 1: 趨勢雷達
    # ════════════════════════════════════
    with tab1:
        # 統計摘要
        c1, c2, c3, c4 = st.columns(4)
        total = len(scored_df)
        s1_count = (scored_df["stage"] == 1).sum() if "stage" in scored_df.columns else 0
        s2_count = (scored_df["stage"] == 2).sum() if "stage" in scored_df.columns else 0
        watchlist = (scored_df["stars"] >= 4).sum()

        c1.metric("掃描標的", total)
        c2.metric("🌅 Stage 1 覺醒", s1_count)
        c3.metric("🚀 Stage 2 加速", s2_count)
        c4.metric("★★★★+ 觀察名單", watchlist)

        st.markdown("---")

        if filtered.empty:
            st.info("目前篩選條件下沒有符合的標的")
        else:
            # 整理表格欄位
            display_cols = ["ticker", "total_score", "stars", "sector", "price"]
            if "stage" in filtered.columns:
                display_cols.insert(3, "stage")

            display_df = filtered[display_cols].copy()
            display_df = display_df.rename(columns={
                "ticker": "代號",
                "total_score": "總分",
                "stars": "星級",
                "sector": "產業",
                "stage": "Stage",
                "price": "股價",
            })

            # 星級轉文字
            display_df["星級"] = display_df["星級"].apply(lambda x: "★" * x + "☆" * (5 - x))

            # Stage 轉 emoji
            if "Stage" in display_df.columns:
                display_df["Stage"] = display_df["Stage"].map(
                    {0: "💤", 1: "🌅", 2: "🚀", 3: "⚠️"}
                ).fillna("?")

            st.dataframe(
                display_df,
                hide_index=True,
                use_container_width=True,
                height=600,
            )

    # ════════════════════════════════════
    # Tab 2: 產業熱力圖
    # ════════════════════════════════════
    with tab2:
        st.markdown('<div class="section-header">產業 × 評分維度 熱力圖</div>', unsafe_allow_html=True)

        if "sector" in scored_df.columns and "dimensions" in scored_df.columns:
            # 計算每個 sector 的平均維度分數
            dim_names = [
                "relative_strength", "price_structure", "volume_analysis",
                "volatility", "sector_momentum", "trend_consistency", "theme_momentum",
            ]
            dim_labels = ["RS", "價格", "成交量", "波動率", "族群", "持續性", "主題"]

            sector_avgs = []
            for sector, group in scored_df.groupby("sector"):
                if len(group) < 3:
                    continue
                row = {"sector": sector}
                for dim in dim_names:
                    vals = group["dimensions"].apply(lambda d: d.get(dim, 0) if isinstance(d, dict) else 0)
                    row[dim] = vals.mean()
                sector_avgs.append(row)

            if sector_avgs:
                heatmap_df = pd.DataFrame(sector_avgs).set_index("sector")
                heatmap_df.columns = dim_labels

                fig = px.imshow(
                    heatmap_df.values,
                    x=dim_labels,
                    y=heatmap_df.index.tolist(),
                    color_continuous_scale="RdYlGn",
                    zmin=20, zmax=80,
                    text_auto=".0f",
                    aspect="auto",
                )
                fig.update_layout(
                    height=500,
                    margin=dict(l=150, r=20, t=30, b=50),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#AAA"),
                )
                st.plotly_chart(fig, use_container_width=True)

        # 產業強度排名
        st.markdown('<div class="section-header">產業強度排名（★★★+ 佔比）</div>', unsafe_allow_html=True)

        if "sector" in scored_df.columns:
            sector_stats = []
            for sector, group in scored_df.groupby("sector"):
                total_in = len(group)
                strong = (group["stars"] >= 3).sum()
                pct = strong / total_in * 100 if total_in > 0 else 0
                avg_score = group["total_score"].mean()
                sector_stats.append({
                    "產業": sector,
                    "標的數": total_in,
                    "★★★+": strong,
                    "強勢比例": f"{pct:.0f}%",
                    "平均分數": f"{avg_score:.1f}",
                })

            sector_stats_df = pd.DataFrame(sector_stats)
            sector_stats_df = sector_stats_df.sort_values("★★★+", ascending=False)
            st.dataframe(sector_stats_df, hide_index=True, use_container_width=True)

    # ════════════════════════════════════
    # Tab 3: 主題追蹤
    # ════════════════════════════════════
    with tab3:
        active = theme_groups.get("active_themes", [])
        cooling = theme_groups.get("cooling_themes", [])
        last_updated = theme_groups.get("last_updated", "尚未掃描")

        st.markdown(f"**最後更新：** {last_updated}")

        if not active and not cooling:
            st.info("主題引擎尚未執行。首次執行 weekly_themes.py 後會出現數據。")
        else:
            if active:
                st.markdown('<div class="section-header">🔥 活躍升溫主題</div>', unsafe_allow_html=True)

                for t in active:
                    acc = t.get("acceleration", 0)
                    status = t.get("status", "")
                    tickers = t.get("tickers", [])
                    reasoning = t.get("reasoning", "")

                    color = "#FF6B6B" if acc > 2.0 else "#FFD93D" if acc > 1.5 else "#00D4AA"

                    with st.expander(f"🔺 {t.get('theme', '?')} — 加速度 {acc:.1f}x"):
                        st.markdown(f"**分類：** {t.get('category', 'N/A')}")
                        st.markdown(f"**狀態：** {status}")
                        st.markdown(f"**首次偵測：** {t.get('first_detected', 'N/A')}")
                        st.markdown(f"**關聯企業：** {', '.join(tickers)}")
                        if reasoning:
                            st.markdown(f"**分析：** {reasoning}")

                        # 顯示關聯企業的評分
                        if tickers and not scored_df.empty:
                            theme_stocks = scored_df[scored_df["ticker"].isin(tickers)]
                            if not theme_stocks.empty:
                                st.dataframe(
                                    theme_stocks[["ticker", "total_score", "stars", "price"]].rename(
                                        columns={"ticker": "代號", "total_score": "總分", "stars": "星級", "price": "股價"}
                                    ),
                                    hide_index=True,
                                )

            if cooling:
                st.markdown('<div class="section-header">❄️ 降溫中的主題</div>', unsafe_allow_html=True)
                for t in cooling[:5]:
                    st.markdown(f"  • {t.get('theme', '?')} (加速度: {t.get('acceleration', 0):.1f}x)")

    # ════════════════════════════════════
    # Tab 4: 個股詳情
    # ════════════════════════════════════
    with tab4:
        # 選股
        ticker_options = scored_df["ticker"].tolist()
        selected = st.selectbox(
            "選擇標的",
            ticker_options,
            index=0 if ticker_options else None,
        )

        if selected:
            row = scored_df[scored_df["ticker"] == selected].iloc[0]

            # 基本資訊
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("總分", f"{row['total_score']:.1f}")
            c2.metric("星級", "★" * row["stars"])
            c3.metric("股價", f"${row['price']:,.2f}")
            stage = row.get("stage", "?")
            stage_text = {0: "💤 沉睡", 1: "🌅 覺醒", 2: "🚀 加速", 3: "⚠️ 衰退"}.get(stage, "?")
            c4.metric("Stage", stage_text)

            st.markdown("---")

            # 雷達圖 + 條狀圖
            col_radar, col_bars = st.columns(2)

            dims = row.get("dimensions", {})
            if isinstance(dims, dict):
                with col_radar:
                    fig = make_radar_chart(dims, selected)
                    st.plotly_chart(fig, use_container_width=True)
                with col_bars:
                    fig = make_score_bars(dims)
                    st.plotly_chart(fig, use_container_width=True)

            # K 線圖
            st.markdown('<div class="section-header">📈 價格走勢</div>', unsafe_allow_html=True)
            chart_days = st.select_slider(
                "回看天數", options=[60, 120, 252, 504], value=252,
                format_func=lambda x: {60: "3個月", 120: "半年", 252: "1年", 504: "2年"}[x],
            )
            fig = make_price_chart(data["ohlcv"], selected, chart_days)
            st.plotly_chart(fig, use_container_width=True)

            # 維度細節
            details = row.get("details", {})
            if isinstance(details, dict) and details:
                st.markdown('<div class="section-header">📋 評分細節</div>', unsafe_allow_html=True)
                for key, val in details.items():
                    st.markdown(f"**{key}**: {val}")

            # 所屬主題
            themes = row.get("themes", [])
            if themes:
                st.markdown(f"**所屬主題：** {', '.join(themes)}")

    # ════════════════════════════════════
    # Tab 5: 系統表現
    # ════════════════════════════════════
    with tab5:
        st.markdown('<div class="section-header">📈 系統歷史表現追蹤</div>', unsafe_allow_html=True)
        st.markdown("追蹤過去被標記為 Stage 1/2 的股票，後續實際報酬表現。")

        try:
            from performance_tracker import (
                track_performance,
                compute_hit_rates,
                format_performance_summary,
            )

            if st.button("🔄 計算歷史表現"):
                with st.spinner("計算中..."):
                    perf_df = track_performance(data["ohlcv"])

                    if perf_df.empty:
                        st.info("尚無足夠歷史快照。系統運行幾天後會開始累積數據。")
                    else:
                        stats = compute_hit_rates(perf_df)

                        # 顯示統計
                        summary_text = format_performance_summary(stats)
                        st.text(summary_text)

                        # 詳細表格
                        st.markdown("### 歷史訊號明細")
                        display = perf_df[[
                            "ticker", "signal_date", "stage", "score",
                            "return_30d", "return_60d", "return_90d",
                        ]].rename(columns={
                            "ticker": "代號", "signal_date": "訊號日期",
                            "stage": "Stage", "score": "當時分數",
                            "return_30d": "30天報酬%",
                            "return_60d": "60天報酬%",
                            "return_90d": "90天報酬%",
                        })
                        st.dataframe(display, hide_index=True, use_container_width=True)
            else:
                st.info("點擊上方按鈕計算歷史表現。需要至少運行數天後才有數據。")

        except Exception as e:
            st.error(f"表現追蹤載入失敗: {e}")

    # ── Footer ──
    st.markdown("---")
    st.markdown(
        '<p style="text-align:center; color:#555;">📡 Trend Radar v1.0 | '
        'Data: Yahoo Finance + Google Trends + Claude API</p>',
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
