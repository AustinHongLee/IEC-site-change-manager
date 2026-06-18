# GUI 照片 PDF 入口回補紀錄

日期：2026-06-18

## 目的

把已完成的現場資料展示管線接回 GUI，讓使用者不用開命令列也能產出：

- `CanonicalReportSet`
- 現場統計單 Excel
- PDF overlay summary
- before/after photo grid PDF

## 入口

位置：

- 紀錄管理頁
- 篩選列
- 新增按鈕：`照片PDF`

按下後會輸出到：

```text
staging/real_attachments_showcase_gui
```

輸出資料夾仍使用 `.iec_real_attachments_showcase` marker 保護：

- 可覆寫自己產出的 showcase。
- 拒絕覆寫沒有 marker 的資料夾。
- 不修改原始 `attachments/`。

## 程式回補

### `control/gui_panels.py`

新增：

- `RecordManagerPanel._export_real_attachments_showcase()`
- `RecordManagerPanel._format_showcase_export_confirmation()`
- `RecordManagerPanel._format_showcase_export_message()`

行為：

- 產出前彈出確認訊息，明確說明輸出資料夾與原始 attachments 不會被修改。
- 呼叫 `run_real_attachments_showcase()`。
- 產出成功後開啟 `showcase/output`。
- 完成訊息列出修改單、焊口、材料列、照片、PDF 份數與資料提醒。

## 測試

新增/擴充：

- `tests/test_billing_panel_logic.py`

覆蓋：

- 確認訊息包含安全輸出與不修改 attachments。
- 完成訊息彙總 PDF 份數與資料提醒。

已跑 focused：

```powershell
python -m pytest -s `
  .\tests\test_billing_panel_logic.py `
  .\tests\test_run_real_attachments_showcase_tool.py `
  .\tests\test_pdf_overlay_renderer.py
```

結果：

- 41 passed

## 實資料驗證

已模擬 GUI 預設輸出位置實跑：

```powershell
python .\tools\run_real_attachments_showcase.py `
  --output .\staging\real_attachments_showcase_gui `
  --overwrite `
  --json
```

結果：

- report_count: 2
- weld_count: 8
- material_row_count: 3
- photo_count: 6
- PDF: 4 份

輸出：

- `staging/real_attachments_showcase_gui/output/real_pdf_overlay_55_2a2.pdf`
- `staging/real_attachments_showcase_gui/output/real_photo_grid_55_2a2.pdf`
- `staging/real_attachments_showcase_gui/output/real_pdf_overlay_0547_AG.pdf`
- `staging/real_attachments_showcase_gui/output/real_photo_grid_0547_AG.pdf`

## 下一步

這個入口仍是「展示/工程版輸出」。

後續要變正式產品，應改成輸出中心：

- 可選輸出類型：統計單、照片表、公司 PDF 表單。
- 可選輸出範圍：全部 attachments、目前篩選、選取修改單。
- 可選輸出位置：預設 output，但允許另存。
