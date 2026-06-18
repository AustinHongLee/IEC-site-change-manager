# Checkpoint C C5 回補紀錄：Opus 19 後續

日期：2026-06-17

## 來源

依 `19_Opus再校準結果_C5_Registry.md` 回補。Opus 結論是「可繼續」，方向無需回改；下一步優先順序是：

1. 正式 import-guard 自動測試。
2. GUI 讀 registry 顯示/判斷舊 COM 輸出狀態。
3. 非 COM PDF 路線。
4. 暫不做 `xlsx_com` CanonicalReport adapter。

## 本次實作

### 1. 正式 import-guard

新增 `tests/test_import_guard.py`：

- 子程序封鎖 `pythoncom`、`win32com`、`win32com.*`。
- 依序 import：
  - `capabilities`
  - `renderer_registry`
  - `canonical_fields`
  - `canonical_report`
  - `template_mapping`
  - `template_dry_run`
  - `xlsx_template_renderer`
  - `site_statistics_exporter`
  - `record_manager`
  - `project_guard`
  - `gui`
- 驗證 import 完成後 `sys.modules` 不含 `pythoncom/win32com`。

### 2. GUI 讀 registry

`control/gui.py` 的舊 COM 產出狀態改讀 `renderer_registry.get_renderer_descriptor("xlsx_com")`：

- GUI 啟動時只做 `probe_com_application=False`，顯示 `unprobed`，不啟動 Excel。
- 使用者按「開始執行」或「重試失敗」時，才做 `probe_com_application=True`。
- `unprobed` 與 `unavailable` 分開顯示：
  - `unprobed`：按需檢查，不灰掉。
  - `unavailable`：停用舊輸出並顯示原因。

### 3. Registry 訊息來源單一化

`renderer_registry.render_with_template(kind="xlsx_com")` 若不可用，錯誤訊息改由 renderer descriptor 產生，不再額外重跑 capability formatter。

## 已驗證

- `tests/test_import_guard.py`
- `tests/test_capabilities.py`
- `tests/test_renderer_registry.py`
- `tests/test_list_renderers_tool.py`

## 後續

下一個高價值工作不是 `xlsx_com` adapter，而是非 COM PDF 路線：

- LibreOffice headless capability probe。
- Excel workbook → PDF 的非 COM converter。
- GUI/CLI 在沒有 Office 時仍可完成主要交付物。
