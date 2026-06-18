# Checkpoint F P0 text overflow 回補紀錄

日期：2026-06-17

## 來源

`34_Opus校準結果_CheckpointF.md` 指出 P0：

`pdf_overlay` 的 `text overflow=error` 在文字放不下時會先截斷 lines，但不回 error，也照樣產出 PDF。這會造成公司表單上的靜默資料遺失。

## 決策

任何輸出模式都不得「無聲丟資料又產成功檔」。

- `text overflow=error`：放不下就回 `text_overflow` error，不產 PDF。
- `clip / shrink / wrap`：允許截斷，但輸出內容需保留可見省略號。
- `table overflow=truncate`：在真正實作前，遇到超列時回 `overflow_mode_unsupported`，不假裝截斷成功。

## 程式回補

### `control/pdf_overlay_renderer.py`

- `_render_text()` 改為回傳 `issues`。
- 文字高度超出 rect 且 `overflow=error` 時，回：
  - `severity=error`
  - `code=text_overflow`
- 單字或字元寬度超出 rect 且 `overflow=error` 時，也回 `text_overflow`。
- page overlay 只要有 error，整體 render 會 `ok=false` 並在寫檔前停止。
- `_field_issue()` 補 `field_index`，方便 UI 或 AI 指出是哪個 field。

### `control/template_dry_run.py`

- `kind=pdf_overlay` 且 table 超列時，當時先讓 `overflow=new_page / truncate` 回 `overflow_mode_unsupported`。
- 後續 `36_CheckpointF_TableNewPage回補紀錄.md` 已把 `overflow=new_page` 升級為真正續頁；目前只有 `overflow=truncate` 仍回 `overflow_mode_unsupported`。
- 其他情境仍保留既有 `table_overflow`。

### `control/renderer_registry.py`

`pdf_overlay` capability detail 已改為：

- 已補 CropBox。
- 已補 `/Rotate`。
- 已補 text overflow fail-fast。
- table `overflow=new_page` 後續已完成；`truncate` 仍明確 unsupported。

## 測試

新增 regression：

- `test_render_pdf_overlay_rejects_text_overflow_error_without_output`
- `test_render_pdf_overlay_reports_unsupported_table_new_page_before_output`（後續已由 `36` 改為 new_page 成功續頁測試）

已跑：

```powershell
python -m pytest -s `
  .\tests\test_pdf_overlay_renderer.py `
  .\tests\test_template_dry_run.py `
  .\tests\test_dry_run_template_tool.py `
  .\tests\test_render_pdf_overlay_tool.py `
  .\tests\test_renderer_registry.py
```

結果：

- 23 passed

## 後續狀態

`36_CheckpointF_TableNewPage回補紀錄.md` 已完成 `table overflow=new_page`。

## 下一步

下一步可以做多頁照片 grid，但契約必須沿用這次修正後的原則：

- 預設仍是 error。
- 只有明確 `overflow=new_page` 才續頁。
- dry-run 必須能預測總頁數與 overflow 結果。
- rows_per_page 是分頁列數權威。
- 若 row_height / rect 高度放不下 rows_per_page，驗證階段就要 error。
