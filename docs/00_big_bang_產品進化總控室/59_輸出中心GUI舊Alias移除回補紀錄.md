# 輸出中心 GUI 舊 Alias 移除回補紀錄

日期：2026-06-22

## 背景

正式 GUI 路徑已改用 `_output_center_*` helper，測試也已不再呼叫 `_showcase_*` 相容 alias。繼續保留這批 alias 會讓後續 AI 在閱讀 `gui_panels.py` 時誤判正式概念仍是 showcase/demo。

## 本次調整

移除 `RecordManagerPanel` 內部 GUI 舊 alias：

- `_show_showcase_result_dialog`
- `_choose_showcase_scope`
- `_showcase_report_keys`
- `_showcase_scope_options`
- `_format_showcase_content_label`
- `_normalize_showcase_output_dir`
- `_showcase_output_items`
- `_showcase_output_groups`
- `_showcase_issue_items`
- `_showcase_issue_action`
- `_format_showcase_issue_tooltip`
- `_showcase_issue_record_ref`
- `_showcase_filters_are_narrowed`
- `_showcase_note_text_is_valid`
- `_format_showcase_export_confirmation`
- `_format_showcase_export_message`

## 邊界

本次不移除 `control/real_attachments_showcase.py` 或 `tools/run_real_attachments_showcase.py`。它們仍是 demo/回歸測試入口，與正式 GUI helper 命名收斂是不同問題。

## 驗收

更新 `tests/test_output_center_ui_smoke.py`，確認 `RecordManagerPanel` 不再暴露這批舊 alias。

下一步需跑：

```powershell
python -m pytest -s -q tests/test_output_center_ui_smoke.py tests/test_billing_panel_logic.py
python -m pytest -s .\tests
```
