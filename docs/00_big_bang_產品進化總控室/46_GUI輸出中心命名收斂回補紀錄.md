# GUI 輸出中心命名收斂回補紀錄

日期：2026-06-18

## 目的

正式輸出中心已改接 `site_output_center`，但 GUI 內部仍保留多個 `_showcase_*` helper 名稱。

本階段把 GUI 主路徑改成 `_output_center_*`，讓 UI 層語意與正式產品命名一致。

## 調整內容

### `control/gui_panels.py`

已正名：

- `_export_site_output_center`
- `_show_output_center_result_dialog`
- `_choose_output_center_scope`
- `_output_center_report_keys`
- `_output_center_scope_options`
- `_format_output_center_content_label`
- `_normalize_output_center_output_dir`
- `_output_center_output_items`
- `_format_output_center_export_confirmation`
- `_format_output_center_export_message`

使用者可見訊息同步改為「輸出中心」語意。

## 相容性

保留舊 alias：

- `_export_real_attachments_showcase`
- `_show_showcase_result_dialog`
- `_choose_showcase_scope`
- `_showcase_report_keys`
- `_showcase_scope_options`
- `_format_showcase_content_label`
- `_normalize_showcase_output_dir`
- `_showcase_output_items`
- `_format_showcase_export_confirmation`
- `_format_showcase_export_message`

目的：

- 保護既有測試
- 保護可能尚未清乾淨的內部呼叫
- 讓命名收斂不和功能變更混在同一刀

## 驗證

已跑 focused：

```powershell
python -m pytest -s `
  .\tests\test_billing_panel_logic.py `
  .\tests\test_run_site_output_center_tool.py `
  .\tests\test_run_real_attachments_showcase_tool.py
```

結果：

- 38 passed

已跑完整測試：

```powershell
python -m pytest -s .\tests
```

結果：

- 328 passed

## 下一步

- 若完整測試穩定，下一個較有價值的方向是把「輸出中心結果清單」再往使用者可理解的統計單/照片/資料 JSON 分組與狀態提示微調。
