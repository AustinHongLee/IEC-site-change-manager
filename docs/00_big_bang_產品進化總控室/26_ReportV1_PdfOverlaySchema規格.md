# report.v1 與 pdf_overlay.v1 契約規格

日期：2026-06-17

## 目的

此文件凍結下一步 PDF overlay 前的契約邊界。

核心原則：

1. 現場資料核心固定為 `report.v1`。
2. 欄位引用固定走 `template_mapping.v1` 與 `canonical_fields.py`。
3. `xlsx_template` 與 `pdf_overlay` 共用 `text / image / table` 三原語。
4. PDF 只新增 target 欄位，不新增另一套資料欄位與 dry-run。
5. 現階段只驗證 schema，不實作 renderer。

## report.v1

`CanonicalReport` 的正式版本為：

```json
{
  "schema_version": "report.v1"
}
```

正式 field-path catalog 由 `control/canonical_fields.py` 輸出，模板只能引用 catalog 內欄位。集合路徑統一使用 `[*]`，例如：

- `welds.rows[*].code`
- `materials.rows[*].component`
- `photos.before[*].path`
- `photos.after[*].path`

`[0]`、`[1]` 這類單筆索引可用於 `text/image`，但不列為 catalog 內的正式列舉；`[0..n]` 只保留為舊模板相容寫法。

## template_mapping.v1

共用原語仍為三種：

| type | source 規則 | 典型用途 |
|---|---|---|
| `text` | 單一 field-path，不可用 `[*]` / `[0..n]` | 報告編號、日期、焊口摘要、材料摘要 |
| `image` | 單一圖片路徑，可用 `[0]` 指定第幾張 | before/after 照片 |
| `table` | 集合 field-path，必須設定 `max_rows` 或 `rows_per_page` | 焊口表、材料表、照片索引 |

`validate_template.py` 先驗 source，再驗 renderer-specific target。

## pdf_overlay.v1

Top-level 必要或建議欄位：

```json
{
  "schema_version": "template_mapping.v1",
  "target_schema_version": "pdf_overlay.v1",
  "kind": "pdf_overlay",
  "base_pdf": "vendor_form.pdf",
  "coordinate_space": "normalized",
  "fields": []
}
```

規則：

- `kind` 必須是 `pdf_overlay`。
- `target_schema_version` 預設為 `pdf_overlay.v1`。
- `coordinate_space` 目前只支援 `normalized`。
- 必須指定 `base_pdf` / `template_pdf` 或 `page_size`，讓 renderer 未來能取得頁面尺寸。
- `rect_norm` 採 `[x, y, width, height]`，全部以 0..1 表示，且不得超出頁面。
- `rect_norm` 相對 PDF 可見區（CropBox）；若沒有 CropBox，renderer 才退回 MediaBox。
- `rect_norm` 原點在可見區左上角，x 向右、y 向下；renderer 內部再轉成 PDF 左下座標。
- renderer 必須以「已套用 `/Rotate` 後的可見幾何」換算座標。
- `page_size` 可作沒有 base PDF 時的頁面尺寸提示；若有 base PDF，不得用 `page_size` 覆蓋 PDF 實際 CropBox/MediaBox 幾何。
- `page` 從 1 開始。

## PDF Target 欄位

### text

```json
{
  "type": "text",
  "source": "report.report_id",
  "page": 1,
  "rect_norm": [0.08, 0.08, 0.24, 0.04],
  "font_size": 10,
  "min_font_size": 7,
  "align": "left",
  "valign": "top",
  "overflow": "shrink"
}
```

允許值：

- `align`: `left / center / right`
- `valign`: `top / middle / bottom`
- `overflow`: `error / shrink / clip / wrap`

若未指定 `overflow`，驗證器會 warning，未來 renderer 預設必須是 `error`。

### image

```json
{
  "type": "image",
  "source": "photos.before[0].path",
  "page": 1,
  "rect_norm": [0.08, 0.20, 0.36, 0.25],
  "fit": "contain"
}
```

允許值：

- `fit`: `contain / cover / stretch`

### table

```json
{
  "type": "table",
  "source": "materials.rows",
  "page": 1,
  "rect_norm": [0.08, 0.52, 0.84, 0.30],
  "rows_per_page": 8,
  "overflow": "new_page",
  "columns": [
    {"source": "component", "header": "零件", "width_norm": 0.50},
    {"source": "qty", "header": "數量", "width_norm": 0.25},
    {"source": "unit", "header": "單位", "width_norm": 0.25}
  ]
}
```

規則：

- `rows_per_page` 或 `max_rows` 必須大於 0。
- `overflow`: `error / new_page / truncate`
- `columns[*].width_norm` 若有設定，總和不可超過 1。

## 明確禁止

`kind=pdf_overlay` 的 field 不可使用 Excel target 欄位：

- `cell`
- `anchor`
- `start_cell`
- `size_cells`
- `max_width_px`
- `max_height_px`
- `sheet`
- `workbook`

原因是 target 欄位必須由 renderer schema 管理，避免 Excel 與 PDF 模板互相污染。

## Registry 狀態

`pdf_overlay` 已登錄於 `renderer_registry`，目前狀態為最小垂直切片：

```json
{
  "kind": "pdf_overlay",
  "available": true,
  "status": "minimal"
}
```

呼叫 `render_with_template(kind="pdf_overlay")` 會分派到 `pdf_overlay_renderer`，可用 `report.v1` 的 `text / image / table` 疊到 base PDF。

已補：

- output result envelope 統一。
- 頁面尺寸換算以 CropBox 可見區為準。
- `/Rotate` 先轉入內容，再做 overlay。
- `text overflow=error` fail-fast。
- `table overflow=new_page` 跨頁續表。
- demo edge matrix 與 rotated base PDF fixture。

## 下一步

renderer 進一步產品化前，還要補：

- 多頁照片自動 grid / pagination。
- 真實公司 PDF 表單與 CJK 字型打包驗證。
- AcroForm 特例後端是否納入 registry 的決策。
