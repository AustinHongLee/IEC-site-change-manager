# Opus 校準請求 Checkpoint F：pdf_overlay minimal renderer

日期：2026-06-17

## 請你審查的範圍

這次只請你看 `pdf_overlay` renderer 從 schema-only 升級到 minimal 的 P0/P1 風險，不要重新展開材料、請款或整體產品路線。

目標是判斷：目前是否可以繼續做 `overflow=new_page`、多頁照片 grid、GUI 接入，還是 renderer 邊界還有必須先補的契約洞。

## 目前已完成

### output result envelope

- 新增 `control/output_result.py`。
- `xlsx_template`、LibreOffice workbook->PDF converter、現場統計單、`pdf_overlay` 都開始回：
  - `result_schema_version`
  - `outputs`
  - `issues`
  - `capabilities`
  - `steps`

### pdf_overlay schema 契約

- `rect_norm` 明確定義為 `[x, y, width, height]`，不是 `[x1, y1, x2, y2]`。
- `page` 是 1-based。
- normalized coordinate 以 PDF CropBox 可見區為基準。
- 左上角為原點，y 向下。
- `page_size_pt` 只可作設計提示或 debug，不得作為座標基準。
- `kind=pdf_overlay` 禁止混用 Excel target 欄位。

### minimal renderer

新增：

- `control/pdf_overlay_renderer.py`
- `tools/render_pdf_overlay.py`

目前支援：

- base PDF / template PDF，相對路徑以 template 所在資料夾解析。
- 無 base PDF 時可用 `page_size` 建 blank PDF。
- render 前先跑 `dry_run_template_for_report()`。
- `text`
- `image`
- `table`
- `debug rect`
- output PDF 後用 pypdf 讀回頁數做 basic validation。

重要實作邊界：

- `_page_geometry()` 使用 CropBox 可見區。
- `_rect_to_points()` 將 normalized top-left/y-down 轉成 PDF points。
- 遇到 `/Rotate` 頁面，先呼叫 pypdf `transfer_rotation_to_content()` 再 overlay。
- overlay 先 `writer.add_page(base_page)`，再對 writer 中的 page `merge_page()`，避免原本 pypdf merge 後被 add_page 複製時的警告。

### renderer registry / capability

`pdf_overlay` 已從 `schema_only` 升級為：

```json
{
  "kind": "pdf_overlay",
  "available": true,
  "status": "minimal"
}
```

Capability detail 已標明：

- 已補 CropBox 與 `/Rotate` regression。
- 仍待進階 overflow、多頁照片與真實表單驗證。

### demo edge matrix

`tools/run_demo_output_smoke.py --edge-matrix` 會產生：

- `0547_AG`：正常完整資料。
- `0601_NO_AFTER`：缺 after 照片，預期 `missing_image_value`。
- `0602_MATERIAL_OVERFLOW`：材料超過 template 預留列，預期 `table_overflow`。
- `0603_MANY_PHOTOS`：before 照片超過照片表預留，預期 `table_overflow`。
- `0604_MULTI_PAGE_PDF`：附件 PDF 兩頁，預期 `attachment_pdf.pages == 2`。
- `edge_pdf_overlay_rotated.template.json` + `rotated_vendor_form.pdf`：`/Rotate 90` base PDF fixture。

### 視覺驗證

已實跑：

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

已目視檢查 `staging/demo_edge_matrix/output/edge_pdf_overlay_rotated_page.png`：

- 文字在左上。
- before / after 圖片在中段。
- 材料表在下方。
- 旋轉底圖轉正後沒有頁外、鏡像或明顯重疊。

Poppler 提醒：

- `STSong-Light` 被替換成 `SimSun`。

此提醒未阻擋 demo，但正式公司包仍需處理 CJK 字型策略。

## 測試結果

已跑：

```powershell
python -m pytest -s .\tests
```

結果：

- 303 collected
- exit code 0

Focused tests：

- `tests/test_pdf_overlay_renderer.py`
- `tests/test_render_pdf_overlay_tool.py`
- `tests/test_renderer_registry.py`
- `tests/test_output_capabilities.py`
- `tests/test_demo_smoke.py`
- `tests/test_run_demo_output_smoke_tool.py`

健康與稽核：

- `python .\control\main.py --health-check`
  - project state: healthy
  - integrity: error=0, warning=1
- warning 是既有資料狀態：2 個 attachments 子資料夾尚未寫入 records。

## 我想請你校準的問題

1. 目前 `pdf_overlay` 從 schema-only 升級為 minimal，是否有 P0 契約洞會阻止下一步做 `overflow=new_page`？
2. `/Rotate` 的做法是 `transfer_rotation_to_content()` 後再 overlay。這對公司表單是否足夠安全？是否需要保留原始 rotate 或另建輸出副本策略？
3. CropBox 作為 normalized coordinate 基準是否正確？還需要處理 MediaBox / ArtBox / TrimBox 的優先序嗎？
4. `overflow=new_page` 下一步應該怎麼做才不破壞共用三原語？
   - table 預設仍 fail，只有明確 `overflow=new_page` 才續頁？
   - 續頁時是否複製 base page、或使用指定 continuation page？
   - rows_per_page 與 rect 高度不一致時，以哪個為準？
5. 多頁照片 grid 應該是 `image` primitive 的擴充、`table` primitive 的一種，還是新增 renderer-specific primitive？
6. AcroForm 可填欄位 PDF 是否應該作為 `pdf_overlay` 的特例，還是 registry 另開 `pdf_form` / `acroform` kind？
7. 在 GUI 暴露 `pdf_overlay` 前，還需要哪些 P0 防呆？
8. output_result.v1 envelope 對 UI、CLI、AI 接管是否足夠？是否需要再加 `artifacts`、`warnings_count` 或 `retryable`？

## 請用這個格式回答

1. 總評：可否繼續做 `overflow=new_page` 與多頁照片。
2. P0 必修：列出會造成錯檔、資料不可追溯、或正式公司表單不可部署的問題。
3. P1 建議：列出可在 GUI 前補，但不阻塞 renderer 下一步的問題。
4. 下一步 3 件事：請明確排序。
5. 不要做的事：列出現在容易過度設計或會打壞主線的方向。
