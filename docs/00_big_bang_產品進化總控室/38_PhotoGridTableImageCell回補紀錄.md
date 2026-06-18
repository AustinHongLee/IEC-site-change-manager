# Photo grid table image cell 回補紀錄

日期：2026-06-17

## 目的

把「多張現場照片」納入正式 template primitive，而不是另開一個只服務 PDF 的特殊功能。

這次選擇延伸 `table`：

- `source` 可使用 `photos.before[*]` / `photos.after[*]`
- column 可宣告 `cell_type: image`
- 圖片格沿用 `fit: contain / cover / stretch`
- 多頁沿用既有 `rows_per_page` + `overflow=new_page`

## 契約

- `cell_type` 預設為 `text`。
- `cell_type: image` 會把該 column 的 `source` 當作圖片路徑欄位。
- 缺圖不阻擋 PDF，回 warning：
  - `missing_image_value`
  - `missing_image_file`
  - `unreadable_image_file`
- schema 會先檢查：
  - table column `cell_type` 只能是 `text` 或 `image`
  - column `fit` 必須是支援值
  - `header_height_pt` 若存在必須大於 0
- `header_height_pt` 可讓圖片列很高時，表頭不跟著變成大列。

## 程式回補

### `control/pdf_overlay_renderer.py`

- 抽出 `_draw_image_value()`，讓 top-level image 與 table image cell 共用同一套圖片繪製、裁切與 warning。
- table data row 依 column `cell_type` 決定畫文字或圖片。
- table summary 會把 image cell 計入 `summary.image`。
- 新增 `header_height_pt` 支援。

### `control/pdf_overlay_schema.py`

- 新增 table image column schema guard。
- 新增 `header_height_pt` 驗證。

### `control/template_dry_run.py`

- dry-run 會檢查 table image cell 的圖片路徑。
- placement 新增 `image_cell_count`。

### `control/real_attachments_showcase.py`

真 attachments showcase 現在會額外輸出 photo grid：

- `templates/real_photo_grid.template.json`
- `output/real_photo_grid_{folder}.pdf`
- 若加 `--png`，同步輸出 PNG 供目視檢查

## 真資料展示結果

已用目前 `attachments/` 兩包 test 資料實跑：

```powershell
python .\tools\run_real_attachments_showcase.py `
  --output .\staging\real_attachments_showcase_cli `
  --overwrite `
  --png `
  --json
```

結果：

- `55_2a2` photo grid: 1 page, 2 張圖片
- `0547_AG` photo grid: 1 page, 4 張圖片
- aggregate: 6 張照片、8 口焊口、3 筆材料

目視檢查：

- `staging/real_attachments_showcase_cli/output/real_photo_grid_0547_AG-1.png`
- `staging/real_attachments_showcase_cli/output/real_photo_grid_55_2a2-1.png`

照片、檔名、before/after 分區皆有輸出；外觀仍是工程展示版，尚未進正式表單美編。

## 測試

已跑 focused：

```powershell
python -m pytest -s `
  .\tests\test_pdf_overlay_renderer.py `
  .\tests\test_pdf_overlay_schema.py `
  .\tests\test_template_dry_run.py `
  .\tests\test_run_real_attachments_showcase_tool.py
```

結果：

- 30 passed

新增/覆蓋重點：

- table image cell 可分頁輸出
- table image cell 缺圖只 warning
- schema 擋錯誤 `cell_type` / `fit`
- dry-run 檢查 table image cell 圖片路徑
- 真 attachments showcase 產出 summary PDF + photo grid PDF

## 下一步

照片 grid 已經證明資料核心能把多張現場照片帶到 PDF。

後續更值得做的是：

- 讓 GUI 產出入口可選「統計單 / photo grid / PDF overlay」。
- 建立正式表單模板規格：公司欄位名稱、座標、照片大小、頁尾簽核欄。
- CJK 字型打包與正式 PDF 視覺驗證。
