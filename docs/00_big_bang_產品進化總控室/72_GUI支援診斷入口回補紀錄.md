# GUI 支援診斷入口回補紀錄

日期：2026-06-22

## 背景

CLI 已可用 `--diagnostics` 產生支援診斷包，但現場或公司一般使用者不一定會打命令。健康檢查頁是最自然的入口。

## 本次新增

- `HealthCheckPanel`
  - 新增 `支援診斷包` 按鈕。
  - 新增 `版本資訊` 按鈕。
  - 診斷包使用既有 `diagnostics.collect_support_bundle(BASE_DIR)`。
- `tests/test_output_center_ui_smoke.py`
  - 檢查主視窗健康頁能看到支援診斷與版本資訊按鈕。
  - 檢查支援診斷按鈕會呼叫 diagnostics 並顯示產出路徑。

## 定位

這一步不改診斷包內容，只把既有 CLI 能力接到 GUI，讓非工程使用者也能回報可分析的 zip。
