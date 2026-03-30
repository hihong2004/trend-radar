# 📡 美股中期趨勢偵測系統 (Trend Radar)

## 系統概述

自動掃描 S&P 500 + Nasdaq 100（約 550 檔）個股，用七維評分系統偵測正在形成中期趨勢（2-6 個月）的標的與產業族群。

**核心功能：**
- 每日自動掃描 550 檔股票，七維度量化評分
- 趨勢生命週期追蹤（沉睡 → 覺醒 → 加速 → 衰退）
- Google Trends 主題自動發現 + Claude API 關聯企業映射
- 產業族群共振偵測
- LINE Messaging API 每日推播觀察名單

## 快速開始

### 1. GitHub 建立 Repo 並上傳檔案

### 2. 設定 GitHub Secrets

`Settings` → `Secrets and variables` → `Actions`：

| Name | 說明 |
|------|------|
| `LINE_CHANNEL_ACCESS_TOKEN` | LINE Messaging API Token |
| `LINE_USER_ID` | 你的 LINE User ID |
| `ANTHROPIC_API_KEY` | Claude API Key |

### 3. 手動觸發測試

`Actions` → `Daily Trend Scan` → `Run workflow`

首次執行需下載全部數據（約 10-15 分鐘），之後增量更新約 5-8 分鐘。

### 4. 自動排程

- **每日掃描**：週一至週五 UTC 23:00（美東 18:00）
- **每週主題**：每週日 UTC 12:00

## 七維評分

| 維度 | 權重 | 說明 |
|------|------|------|
| 相對強度 | 22% | vs SPY 超額報酬排名 |
| 價格結構 | 18% | Minervini Trend Template |
| 成交量異常 | 18% | 量能爆發 + 量價配合 |
| 波動率突破 | 12% | Bollinger Squeeze |
| 族群共振 | 10% | 同 Sector 強勢比例 |
| 趨勢持續性 | 10% | 上漲週比 + 回撤深度 |
| 主題熱度 | 10% | Google Trends 升溫主題 |

## 命令列用法

```bash
python daily_scan.py --dry-run       # 測試（不發 LINE）
python daily_scan.py --always-send   # 正式發送
python weekly_themes.py --dry-run    # 主題掃描測試
```

## 免責聲明

僅供研究與教育用途，不構成投資建議。
