# note 提醒內建編輯入口回補紀錄

日期：2026-06-18

## 目的

上一階段資料提醒已可依 `code` 提供處理入口，其中 `note` 先以開啟附件資料夾處理。

本階段將 `note` 提醒升級為內建編輯入口，讓使用者不必離開程式就能補齊現場說明。

## 調整內容

### `control/gui_panels.py`

`note` issue action 從：

```text
open_folder / 開啟資料夾補 note
```

改為：

```text
edit_note / 編輯 note.txt
```

按下輸出中心結果 dialog 的 `處理提醒` 時：

1. 由 `record_ref` 找到對應 attachments 資料夾
2. 讀取既有 `note.txt`
3. 開啟小型文字編輯視窗
4. 儲存時驗證不可空白、不可保留 `請填寫` 或 `#` 樣板文字
5. 以 `.tmp + os.replace` 寫回 `note.txt`

安全邊界：

- 只寫入目標資料夾的 `note.txt`
- 不修改其他 attachments 檔案
- 不修改 `records.json`
- 目標資料夾不存在時不自動建立，避免寫錯位置

## 新增 helper

- `_edit_output_center_note(record_ref, parent=...)`
- `_read_output_center_note_text(note_path)`
- `_write_output_center_note_text(note_path, text)`
- `_output_center_note_text_is_valid(text)`

保留相容 alias：

- `_showcase_note_text_is_valid`

## 測試

新增/調整：

- `test_record_manager_output_center_note_text_helpers`
- `test_record_manager_output_center_issue_actions_by_code` 改驗證 `note -> edit_note`
- `test_record_manager_output_center_groups_outputs_and_warnings` 改驗證 `編輯 note.txt`

已跑 focused：

```powershell
python -m pytest -s `
  .\tests\test_billing_panel_logic.py `
  .\tests\test_canonical_report.py `
  .\tests\test_run_site_output_center_tool.py `
  .\tests\test_run_real_attachments_showcase_tool.py
```

結果：

- 49 passed

已跑完整測試：

```powershell
python -m pytest -s .\tests
```

結果：

- 336 passed

## 下一步

- 若穩定，可再把 before/after 照片提醒接到既有加圖流程，而不是只開資料夾。
