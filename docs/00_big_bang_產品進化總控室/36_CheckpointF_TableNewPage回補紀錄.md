# Checkpoint F table overflow=new_page 回補紀錄

日期：2026-06-17

## 來源

`34_Opus校準結果_CheckpointF.md` 建議在修完 `text overflow=error` fail-fast 後，下一步做 `table overflow=new_page`。

## 契約

- table 預設仍是 `overflow=error`。
- 只有明確設定 `overflow=new_page` 時才續頁。
- `rows_per_page` / `max_rows` 是分頁列數權威。
- 續頁預設複製同一張 base page。
- 若模板指定 `continuation_page`，續頁複製該 1-based base page。
- `overflow=truncate` 仍未實作；遇到超列時回 `overflow_mode_unsupported`，不產 PDF。
- 若 `row_height_pt * rows_per_page` 加上 header 後超出 rect 高度，回 `table_row_height_overflow`，不產 PDF。

## 程式回補

### `control/template_dry_run.py`

- `kind=pdf_overlay` 且 `overflow=new_page` 時，不再回 unsupported。
- dry-run placement 會回：
  - `overflow`
  - `overflow_count`
  - `render_pages`
- `overflow=truncate` 仍回 `overflow_mode_unsupported`。

### `control/pdf_overlay_renderer.py`

新增 render plan：

- 先把 template fields 按 base page 分組。
- table 若未超列，照原頁 render。
- table 若超列且 `overflow=new_page`：
  - 將 rows 依 `rows_per_page` 切 chunk。
  - 第一個 chunk 留在原頁。
  - 後續 chunk 產生 continuation jobs。
  - continuation jobs 複製原 page 或 `continuation_page` 指定頁。
- 輸出頁數超過 guard 時回 `pdf_overlay_page_guard`。
- 每個 continuation page 仍走同一套 CropBox、`/Rotate`、overlay merge 流程。

### `control/pdf_overlay_schema.py`

- `continuation_page` 若存在，必須是正整數。
- `row_height_pt` 若存在，必須大於 0。

## 測試

新增 regression：

- `test_render_pdf_overlay_table_new_page_adds_continuation_pages`
- `test_render_pdf_overlay_table_new_page_can_use_continuation_page`
- `test_render_pdf_overlay_reports_unsupported_table_truncate_before_output`
- `test_render_pdf_overlay_rejects_table_row_height_overflow_without_output`
- `test_dry_run_pdf_overlay_new_page_predicts_render_pages`
- `test_dry_run_pdf_overlay_truncate_is_explicitly_unsupported`

已跑：

```powershell
python -m pytest -s `
  .\tests\test_pdf_overlay_renderer.py `
  .\tests\test_template_dry_run.py `
  .\tests\test_pdf_overlay_schema.py `
  .\tests\test_render_pdf_overlay_tool.py `
  .\tests\test_renderer_registry.py
```

結果：

- 29 passed

後續完整驗證：

- focused 41 passed
- full test 310 passed

## 視覺驗證

已產生 3 頁 demo PDF：

```powershell
python .\tools\run_demo_output_smoke.py --output .\staging\demo_output --overwrite --json
```

再以 demo report 手動把 `materials.rows` 擴成 3 列、把 `rows_per_page` 改為 1，呼叫 `render_pdf_overlay_for_report()` 產出：

- `staging/demo_output/output/demo_pdf_overlay_new_page.pdf`

結果：

- `ok: true`
- `pdf_validation.pages: 3`
- dry-run table placement `render_pages: 3`
- `summary.rows: 3`

已用 Poppler 轉 PNG：

```powershell
pdftoppm -png `
  .\staging\demo_output\output\demo_pdf_overlay_new_page.pdf `
  .\staging\demo_output\output\demo_pdf_overlay_new_page
```

目視檢查：

- 第 1 頁保留原本文字、照片與第 1 列材料。
- 第 2 頁只渲染第 2 列材料，表格落點一致。
- 第 3 頁只渲染第 3 列材料，表格落點一致。
- 沒有把超出資料擠進同一頁，也沒有頁外或重疊。

Poppler 仍有 `STSong-Light -> SimSun` 字型替代提醒；這屬於 CJK 字型打包議題，未阻擋本次 new_page 驗證。

## 下一步

多頁照片 grid 可以建立在 table primitive 上：

- source 使用 `photos.before[*]` 或 `photos.after[*]`。
- columns 可宣告 image cell。
- 分頁沿用 `rows_per_page` + `overflow=new_page`。
- 不新增第 4 種 primitive。
