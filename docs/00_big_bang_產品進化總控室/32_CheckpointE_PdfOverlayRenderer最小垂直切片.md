# Checkpoint E pdf_overlay renderer 最小垂直切片

日期：2026-06-17

## 目標

在 `report.v1 / template_mapping.v1 / pdf_overlay.v1`、`output_result.v1`、demo edge matrix 都就位後，先做一個可驗證的 PDF overlay renderer 最小垂直切片。

此階段不是完整產品版 renderer，而是先證明：

- base PDF 可讀。
- normalized `rect_norm` 可換算到 PDF 頁面。
- `text / image / table` 三原語可疊到 PDF。
- 產出後 PDF 可被 pypdf 讀回。
- 可用 Poppler 轉 PNG 目視檢查。

## 新增程式

### `control/pdf_overlay_renderer.py`

新增 `render_pdf_overlay_for_report(report, template, output_path, template_dir=None)`：

- 先跑 `dry_run_template_for_report()`。
- 讀 `base_pdf` / `template_pdf`，相對路徑以 `template_dir` 解析。
- 支援無 base PDF 時用 `page_size` 建 blank PDF。
- 以 CropBox 可見區換算 `rect_norm: [x,y,width,height]`。
- 若頁面有 `/Rotate`，先呼叫 pypdf `transfer_rotation_to_content()`。
- 用 reportlab 建 overlay page，再用 pypdf `merge_page()` 疊回 base PDF。
- 產出後用 pypdf 回讀頁數。

支援原語：

- `text`
  - `font_size`
  - `min_font_size`
  - `align`
  - `valign`
  - `overflow: shrink / wrap / clip / error`
- `image`
  - `fit: contain / cover / stretch`
  - 圖片缺失時畫 placeholder 並回 warning
- `table`
  - `rows_per_page` / `max_rows`
  - `overflow=new_page`
  - `continuation_page`
  - `columns`
  - `width_norm`
  - header row

### `tools/render_pdf_overlay.py`

新增 CLI：

```powershell
python .\tools\render_pdf_overlay.py TEMPLATE_JSON OUTPUT_PDF --report-set REPORT_SET_JSON --json
```

可用於人工測試公司 PDF template，不必進 GUI。

## Registry

`renderer_registry` 的 `pdf_overlay` 狀態：

```json
{
  "kind": "pdf_overlay",
  "available": true,
  "status": "minimal"
}
```

`render_with_template(kind="pdf_overlay")` 現在會實際分派到 `pdf_overlay_renderer`。

## Capability

`output_capabilities.py` 新增：

- `key=pdf_overlay`
- `label=PDF Overlay 模板輸出`
- `status=minimal`
- `optional=true`

## Demo

`run_demo_output_smoke()` 會在 `templates/vendor_form.pdf` 產一張 base PDF，讓 `demo_pdf_overlay.template.json` 可直接渲染。

實跑：

```powershell
python .\tools\render_pdf_overlay.py `
  .\staging\demo_output\templates\demo_pdf_overlay.template.json `
  .\staging\demo_output\output\demo_pdf_overlay.pdf `
  --report-set .\staging\demo_output\records\demo_canonical_report_set.json `
  --json
```

結果：

- `ok: true`
- `pdf_validation.pages: 1`
- `outputs[0].kind: pdf_overlay`
- `summary.text: 2`
- `summary.image: 2`
- `summary.table: 1`
- `summary.rows: 2`

## 視覺驗證

用 Poppler：

```powershell
pdftoppm -png -singlefile .\staging\demo_output\output\demo_pdf_overlay.pdf .\staging\demo_output\output\demo_pdf_overlay_page
```

已目視檢查：

- 報告資料夾文字出現在左上。
- 焊口摘要出現在下一列。
- before / after 兩張圖片出現在中段。
- 材料表出現在下方。
- PDF 可讀且版面沒有明顯重疊。

## CropBox 與 Rotate 回補

2026-06-17 已補幾何 regression：

- `_page_geometry()` 以 CropBox 可見區換算 normalized coordinates。
- `_rect_to_points()` 固定使用 `rect_norm: [x,y,width,height]`，左上原點、y 向下。
- `/Rotate` 頁面 render 前先呼叫 pypdf `transfer_rotation_to_content()`。
- 測試用 `/Rotate 90` base PDF 產出後，確認輸出 PDF `/Rotate` 歸零、頁面尺寸轉正且文字可抽取。
- 另用 debug rect + Poppler PNG 檢查旋轉頁面左上落點仍在預期區域。

實跑 rotated demo：

```powershell
python .\tools\run_demo_output_smoke.py --output .\staging\demo_edge_matrix --overwrite --edge-matrix --json

python .\tools\render_pdf_overlay.py `
  .\staging\demo_edge_matrix\templates\edge_pdf_overlay_rotated.template.json `
  .\staging\demo_edge_matrix\output\edge_pdf_overlay_rotated.pdf `
  --report-set .\staging\demo_edge_matrix\records\edge_canonical_report_set.json `
  --report 0547_AG `
  --json

pdftoppm -png -singlefile `
  .\staging\demo_edge_matrix\output\edge_pdf_overlay_rotated.pdf `
  .\staging\demo_edge_matrix\output\edge_pdf_overlay_rotated_page
```

已目視檢查 `staging/demo_edge_matrix/output/edge_pdf_overlay_rotated_page.png`：旋轉底圖經轉正後，文字、before/after 圖片與材料表皆在預期位置。

## Checkpoint F P0 回補

依 `34_Opus校準結果_CheckpointF.md`，`text overflow=error` 不可無聲截斷後仍產 PDF。

已補：

- `_render_text()` 改為回傳 issues。
- `overflow=error` 遇到高度或寬度放不下時，回 `text_overflow` error。
- page overlay 有 error 時整體 render `ok=false`，不寫出會誤導的 PDF。
- `clip / shrink / wrap` 若截斷，仍保留省略號作為可見標記。
- `table overflow=truncate` 在真正實作前若遇到資料超列，dry-run / renderer 會回 `overflow_mode_unsupported`，不再混成泛用 `table_overflow`。

新增 regression：

- 長文字小框 + `overflow=error`：必須 `ok=false`，不得產出 PDF。
- table 超列 + `overflow=truncate`：必須回 `overflow_mode_unsupported`，不得產出 PDF。

## Table new_page 回補

2026-06-17 已補 `table overflow=new_page`：

- dry-run 會預測 `render_pages`。
- renderer 會依 `rows_per_page` 切 chunk。
- 第一個 chunk 留在原頁。
- 後續 chunk 會複製原 base page。
- 若指定 `continuation_page`，續頁會複製該 base page。
- `row_height_pt` 與 rect 高度不相容時回 `table_row_height_overflow`，不產 PDF。

Poppler 有字型替代提醒：

- `STSong-Light` 被替換成 `SimSun`

這不阻擋目前 demo，但正式公司包應把中文字型策略列入打包驗收。

## 測試

- `tests/test_pdf_overlay_renderer.py`
- `tests/test_render_pdf_overlay_tool.py`
- `tests/test_renderer_registry.py`
- `tests/test_list_renderers_tool.py`
- `tests/test_import_guard.py`
- `tests/test_output_capabilities.py`
- `tests/test_check_output_capabilities_tool.py`

## 尚未做

- 尚未把多張照片自動展成多頁 grid。
- 尚未做 pixel-level 或 image diff regression。
- 尚未接 GUI。
- 尚未用真實公司 PDF 表單校準字型、欄位大小與視覺精度。
