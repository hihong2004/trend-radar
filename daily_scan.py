"""
daily_scan.py — 每日趨勢掃描腳本
由 GitHub Actions 每個交易日收盤後觸發。

執行流程：
  1. 增量更新 550 檔 OHLCV 數據
  2. 七維評分計算
  3. Stage 判定
  4. 發送 LINE 推播
  5. 儲存每日快照

Usage:
  python daily_scan.py              # 正常執行
  python daily_scan.py --dry-run    # 不發送 LINE，僅印出報告
  python daily_scan.py --full       # 強制完整下載數據（不用快取）
  python daily_scan.py --always-send  # 不管有無變化都發 LINE
"""

import sys
import argparse
import logging
import json
import os

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def load_theme_info() -> dict:
    """載入主題群組資訊（由 weekly_themes.py 產生）"""
    import config
    path = os.path.join(config.BASE_DIR, "themes", "theme_groups.json")
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def main():
    parser = argparse.ArgumentParser(description="趨勢雷達 — 每日掃描")
    parser.add_argument("--dry-run", action="store_true", help="不發送 LINE")
    parser.add_argument("--full", action="store_true", help="強制完整下載數據")
    parser.add_argument("--always-send", action="store_true", help="不管有無變化都發送")
    args = parser.parse_args()

    try:
        logger.info("=" * 50)
        logger.info("🚀 開始每日趨勢掃描")
        logger.info("=" * 50)

        # Step 1: 載入數據
        from data_pipeline import load_all_data
        from scoring.composite import (
            score_all_tickers,
            determine_stages,
            get_stage_transitions,
            get_watchlist,
            save_daily_snapshot,
        )
        from alerts.formatter import format_daily_report, format_short_alert
        from alerts.line_alert import send_line_alert

        logger.info("📦 載入數據...")
        data = load_all_data(full_refresh=args.full)

        ohlcv = data["ohlcv"]
        if ohlcv.empty:
            logger.error("❌ OHLCV 數據為空，終止")
            sys.exit(1)

        logger.info(f"  {ohlcv['ticker'].nunique()} 檔標的, {len(ohlcv)} 筆數據")

        # Step 2: 七維評分
        logger.info("📊 開始七維評分...")
        scored_df = score_all_tickers(data)

        if scored_df.empty:
            logger.error("❌ 評分結果為空，終止")
            sys.exit(1)

        logger.info(f"  評分完成: {len(scored_df)} 檔")

        # Step 3: Stage 判定
        logger.info("🔄 Stage 判定...")
        scored_df = determine_stages(scored_df)

        transitions = get_stage_transitions(scored_df)
        new_s1 = transitions.get("new_stage1", [])
        new_s2 = transitions.get("new_stage2", [])
        decay_s3 = transitions.get("decay_stage3", [])

        logger.info(f"  新 Stage 1: {len(new_s1)} 檔")
        logger.info(f"  新 Stage 2: {len(new_s2)} 檔")
        logger.info(f"  衰退 Stage 3: {len(decay_s3)} 檔")

        # Step 4: 載入主題資訊
        theme_info = load_theme_info()
        active_themes = len(theme_info.get("active_themes", []))
        logger.info(f"🌐 活躍主題: {active_themes} 個")

        # Step 5: 格式化報告
        has_changes = bool(new_s1 or new_s2 or decay_s3)

        if has_changes:
            report = format_daily_report(scored_df, transitions, theme_info)
        else:
            report = format_short_alert(scored_df, transitions)

        # Step 6: 儲存快照
        save_daily_snapshot(scored_df)

        # Step 7: 發送或顯示
        if args.dry_run:
            logger.info("=" * 50)
            logger.info("📋 [DRY RUN] 報告內容：")
            logger.info("=" * 50)
            print("\n" + report + "\n")

            # 印出一些統計
            watchlist = get_watchlist(scored_df, min_stars=4)
            logger.info(f"\n📊 統計摘要:")
            logger.info(f"  ★★★★+ 觀察名單: {len(watchlist)} 檔")
            if not watchlist.empty:
                logger.info(f"  Top 10:")
                for _, r in watchlist.head(10).iterrows():
                    logger.info(
                        f"    {r['ticker']:6s} {r['total_score']:5.1f} "
                        f"{'★'*r['stars']} Stage {r.get('stage', '?')}"
                    )
        else:
            should_send = args.always_send or has_changes
            watchlist_count = (scored_df["stars"] >= 4).sum()

            # 即使沒有 stage 變化，如果觀察名單 > 0 也發送精簡版
            if not should_send and watchlist_count > 0:
                should_send = True

            if should_send:
                logger.info("📤 發送 LINE 推播...")
                success = send_line_alert(report)
                if success:
                    logger.info("✅ LINE 推播完成")
                else:
                    logger.error("❌ LINE 推播失敗")
                    sys.exit(1)
            else:
                logger.info("📭 無重大變化且無觀察名單，不推播")

        logger.info("🏁 每日掃描完成")

    except Exception as e:
        logger.exception(f"💥 掃描失敗: {e}")

        # 嘗試發送錯誤通知
        if not args.dry_run:
            try:
                from alerts.line_alert import send_line_alert
                send_line_alert(f"⚠️ 趨勢雷達掃描錯誤\n\n{str(e)[:500]}")
            except Exception:
                pass

        sys.exit(1)


if __name__ == "__main__":
    main()
