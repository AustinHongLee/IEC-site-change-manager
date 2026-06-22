# APP 版本資訊回補紀錄

日期：2026-06-22

## 背景

EXE 產品化後，使用者回報問題時需要明確知道自己執行的是哪個版本。原本 GUI 標題內有手寫版本字串，但 CLI、health-check 與未來診斷頁沒有共同來源。

## 本次新增

- `control/app_info.py`
  - `APP_ID`
  - `APP_NAME`
  - `APP_LOCAL_NAME`
  - `APP_VERSION`
  - `APP_CHANNEL`
  - CLI、GUI、診斷用格式化函式
- `control/main.py`
  - 新增 `--version`
  - `--health-check` / `--audit-integrity` 頭部印出 APP identity
- `control/gui.py`
  - 視窗標題改用 `app_info.format_window_title()`
- `tests/test_app_info.py`

## 驗證目標

後續使用者若截圖、貼 health-check、或回報 exe 啟動問題，至少能帶出同一份版本資訊。
