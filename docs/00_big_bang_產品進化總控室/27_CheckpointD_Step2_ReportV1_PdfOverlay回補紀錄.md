# Checkpoint D Step2 report.v1 / pdf_overlay schema 回補紀錄

日期：2026-06-17

## 來源

依 `24_Opus校準結果_CheckpointD.md` 的下一步建議：

- 先凍結 `report.v1`、field-path catalog 與完整度資料。
- 先寫 `pdf_overlay` schema 規格，擴充 `validate_template` 接受 PDF 落點欄位。
- 在 schema 與驗證完成前，不寫 PDF renderer。

## 本次回補

### `control/pdf_overlay_schema.py`

新增 `pdf_overlay.v1` target schema 驗證：

- `kind=pdf_overlay`
- `target_schema_version=pdf_overlay.v1`
- `coordinate_space=normalized`
- `base_pdf/template_pdf/page_size`
- `page`
- `rect_norm: [x, y, width, height]`
- text overflow / font size / align / valign
- image fit
- table rows_per_page / overflow / columns width_norm
- 同頁 rect overlap
- 阻擋 Excel target 欄位混入 PDF template

### `control/template_mapping.py`

- 保留 source mapping 為 renderer-neutral。
- 當 `kind=pdf_overlay` 時，額外呼叫 PDF target schema validator。
- `validate_template.py` 因此可直接驗證 PDF overlay template。

### `control/renderer_registry.py`

- `pdf_overlay` 已登錄為 renderer kind。
- 狀態是 `schema_only`。
- `render_with_template(kind="pdf_overlay")` 回傳 `renderer_schema_only`，不產檔。

### `control/demo_smoke.py`

- demo 專案會新增 `templates/demo_pdf_overlay.template.json`。
- demo smoke 會驗證該 PDF overlay template schema。
- demo smoke 仍只產 xlsx_template workbook 與現場統計單，不產 PDF overlay。

## 文件

- `26_ReportV1_PdfOverlaySchema規格.md`
- `02_決策紀錄.md`
- `03_Phase0_落地開發板.md`
- `09_現場資料核心與多格式輸出前導書.md`

## Checkpoint E 規格釐清

依 `29_Opus校準結果_CheckpointE.md` 回補：

- `rect_norm` 凍結為 `[x,y,width,height]`，不是 `[x0,y0,x1,y1]`。
- `page` 凍結為 1-based。
- `rect_norm` 相對 PDF 可見區 CropBox；無 CropBox 時才退回 MediaBox。
- 原點為可見區左上，x 向右、y 向下。
- renderer 必須以已套用 `/Rotate` 後的可見幾何換算座標。
- `page_size` 只能是無 base PDF 時的尺寸提示；不能覆蓋 base PDF 實際幾何。

## 測試

- `tests/test_pdf_overlay_schema.py`
- `tests/test_validate_template_tool.py`
- `tests/test_renderer_registry.py`
- `tests/test_list_renderers_tool.py`
- `tests/test_demo_smoke.py`
- `tests/test_import_guard.py`

## 後續狀態更新

Checkpoint E 之後已新增 `pdf_overlay` minimal renderer。此文件仍保留 schema-only 階段的脈絡；目前最新狀態請看 `32_CheckpointE_PdfOverlayRenderer最小垂直切片.md`。

## 尚未完整產品化

- output result envelope 已有 v1，但 GUI 尚未全面改讀 envelope。
- PDF overlay 已完成 demo 視覺驗證，但尚未建立自動化 image diff / pixel regression。
- 多頁照片 / 缺 after / table overflow 的 demo edge matrix 已建立，但尚未全部接成 renderer 視覺 regression。
- 尚未決策 AcroForm 特例後端。
