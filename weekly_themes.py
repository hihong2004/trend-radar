"""
weekly_themes.py — 每週主題掃描腳本
由 GitHub Actions 每週日觸發，執行：
  1. Google Trends 掃描種子關鍵字
  2. 識別升溫主題
  3. Claude API 映射主題→企業
  4. 更新 theme_groups.json
  5. （選擇性）發送 LINE 主題更新摘要

Usage:
  python weekly_themes.py              # 正常執行
  python weekly_themes.py --dry-run    # 不發送 LINE
  python weekly_themes.py --notify     # 強制發送 LINE 摘要
"""

import sys
import argparse
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def format_theme_summary(scan_result: dict) -> str:
    """格式化主題掃描結果為 LINE 訊息"""
    rising = scan_result.get("rising_themes", [])
    mappings = scan_result.get("mappings", [])
    discoveries = scan_result.get("new_discoveries", [])
    total = scan_result.get("total_scanned", 0)

    lines = [
        "═" * 20,
        "🌐 主題雷達週報",
        f"📅 {scan_result.get('scan_date', 'N/A')}",
        f"掃描 {total} 個關鍵字",
        "═" * 20,
    ]

    if not rising:
        lines.append("\n📭 本週無新升溫主題")
    else:
        lines.append(f"\n🔥 {len(rising)} 個升溫主題\n")

        for m in mappings:
            theme = m.get("theme", m.get("keyword", "?"))
            acc = m.get("acceleration", 0)
            tickers = m.get("tickers", [])
            category = m.get("category", "")

            lines.append(f"🔺 {theme} ({acc:.1f}x)")
            if category:
                lines.append(f"   分類: {category}")
            if tickers:
                lines.append(f"   關聯: {', '.join(tickers[:8])}")
                if len(tickers) > 8:
                    lines.append(f"         ...等 {len(tickers)} 檔")
            lines.append("")

    if discoveries:
        lines.append("💡 新發現的關聯查詢")
        for d in discoveries[:10]:
            lines.append(f"  • {d}")

    lines.append(f"\n{'═' * 20}")
    lines.append("📡 Trend Radar Theme Engine")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="每週主題掃描")
    parser.add_argument("--dry-run", action="store_true", help="不發送 LINE")
    parser.add_argument("--notify", action="store_true", help="強制發送 LINE 摘要")
    args = parser.parse_args()

    try:
        logger.info("=" * 50)
        logger.info("🚀 開始每週主題掃描")
        logger.info("=" * 50)

        from themes.theme_mapper import run_theme_discovery

        scan_result = run_theme_discovery()

        # 格式化摘要
        summary = format_theme_summary(scan_result)

        rising_count = len(scan_result.get("rising_themes", []))

        if args.dry_run:
            logger.info("=" * 50)
            logger.info("📋 [DRY RUN] 主題摘要：")
            logger.info("=" * 50)
            print("\n" + summary + "\n")
        else:
            # 有升溫主題或強制通知時發送 LINE
            if rising_count > 0 or args.notify:
                try:
                    from alerts.line_alert import send_line_alert
                    success = send_line_alert(summary)
                    if success:
                        logger.info("✅ LINE 主題摘要已發送")
                    else:
                        logger.error("❌ LINE 發送失敗")
                except ImportError:
                    logger.info("📋 LINE 模組尚未建立，顯示摘要：")
                    print("\n" + summary + "\n")
            else:
                logger.info("📭 無升溫主題，不發送 LINE")

        logger.info("🏁 主題掃描完成")

    except Exception as e:
        logger.exception(f"💥 主題掃描失敗: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
