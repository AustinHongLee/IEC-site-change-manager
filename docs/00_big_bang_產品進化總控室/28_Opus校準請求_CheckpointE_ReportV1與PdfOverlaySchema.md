# Opus 校準請求 Checkpoint E：report.v1 與 pdf_overlay schema-only

日期：2026-06-17

## 這次請你校準的焦點

Checkpoint D 後，我們沒有直接寫 `pdf_overlay` renderer，而是先做兩件事：

1. 補完 LibreOffice converter 的 P0 安全邊界。
2. 鎖住 `report.v1 / template_mapping.v1 / pdf_overlay.v1` 的 schema-only 階段。

我想請你用「準備進 renderer 前」的角度檢查：現在是否已經可以開始寫 `pdf_overlay` renderer，還是還有 P0/P1 契約洞要先補？

## 已完成回補一：LibreOffice P0

### 程式

- `control/workbook_pdf_converter.py`
  - `subprocess.run(... timeout=...)` 改成 `_run_libreoffice_command()`。
  - timeout 會丟 `LibreOfficeCommandTimeout`。
  - timeout 時嘗試終止整個 LibreOffice 程序樹。
  - Windows 用 `taskkill /T /F` fallback `process.kill()`。
  - timeout 回 `libreoffice_timeout` failure dict。
  - OSError / PermissionError / FileNotFoundError 回 `libreoffice_spawn_failed` failure dict。

### 文件

- `25_CheckpointD_Opus24_P0回補紀錄.md`
- `02_決策紀錄.md`
- `21_非COM_PDF_LibreOffice回補紀錄.md`

### 決策

LibreOffice 部署策略已拍板：

- portable LibreOffice 隨公司版打包為主。
- `settings.json` 的 `paths.soffice_path` 作 fallback。
- 已安裝 LibreOffice 可容忍自動搜尋或指定路徑。
- portable 打包與真機視覺驗證前，PDF 不能是唯一交付物。

## 已完成回補二：pdf_overlay schema-only

### 新增程式

- `control/pdf_overlay_schema.py`
  - `PDF_OVERLAY_SCHEMA_VERSION = "pdf_overlay.v1"`
  - 驗證：
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

### 接入點

- `control/template_mapping.py`
  - source validation 仍保持 renderer-neutral。
  - `kind=pdf_overlay` 時額外呼叫 target schema validator。
  - `tools/validate_template.py` 因此可驗 PDF overlay template。

- `control/renderer_registry.py`
  - registry 已認得 `pdf_overlay`。
  - 狀態為 `schema_only`。
  - `render_with_template(kind="pdf_overlay")` 回 `renderer_schema_only`。
  - 不產 PDF，不假裝可用。

- `control/demo_smoke.py`
  - demo 專案會產出 `templates/demo_pdf_overlay.template.json`。
  - demo smoke 會驗證此 template schema。
  - demo smoke 仍只產 xlsx_template workbook 與現場統計單。

## 新文件

- `26_ReportV1_PdfOverlaySchema規格.md`
- `27_CheckpointD_Step2_ReportV1_PdfOverlay回補紀錄.md`

## 目前 schema 範例

```json
{
  "schema_version": "template_mapping.v1",
  "target_schema_version": "pdf_overlay.v1",
  "kind": "pdf_overlay",
  "base_pdf": "vendor_form.pdf",
  "coordinate_space": "normalized",
  "fields": [
    {
      "type": "text",
      "source": "report.folder",
      "page": 1,
      "rect_norm": [0.08, 0.08, 0.28, 0.04],
      "font_size": 10,
      "overflow": "shrink"
    },
    {
      "type": "image",
      "source": "photos.before[0].path",
      "page": 1,
      "rect_norm": [0.08, 0.24, 0.38, 0.28],
      "fit": "contain"
    },
    {
      "type": "table",
      "source": "materials.rows",
      "page": 1,
      "rect_norm": [0.08, 0.60, 0.84, 0.25],
      "rows_per_page": 8,
      "overflow": "new_page",
      "columns": [
        {"source": "component", "header": "零件", "width_norm": 0.34},
        {"source": "size", "header": "尺寸", "width_norm": 0.18},
        {"source": "sch", "header": "SCH", "width_norm": 0.18},
        {"source": "qty", "header": "數量", "width_norm": 0.15},
        {"source": "unit", "header": "單位", "width_norm": 0.15}
      ]
    }
  ]
}
```

## 測試結果

已跑：

- `python -m pytest -s tests`
  - collected 293
  - exit code 0
- `python .\tools\run_demo_output_smoke.py --output .\staging\demo_output --overwrite --json`
  - `ok: true`
  - `pdf_overlay_template.ok: true`
- `python .\tools\validate_template.py .\staging\demo_output\templates\demo_pdf_overlay.template.json`
  - 通過模板驗證
- `python .\control\main.py --health-check`
  - healthy
- `python .\tools\audit_data.py`
  - error=0, warning=1
  - warning 是既有 attachments 尚未產 records：`20250820/55_2a2`、`20260112/0547_AG`
- `git diff --check`
  - exit code 0
  - 只有既有 LF/CRLF warning

## 請你重點校準

1. `pdf_overlay.v1` 目前使用 `rect_norm: [x, y, width, height]`，是否應改成 `[x1, y1, x2, y2]`，或目前版本可接受？
2. `coordinate_space=normalized` 是否足夠？是否需要現在就把 `page_size_pt` / 真實 PDF box 概念放進 schema？
3. `pdf_overlay` 目前阻擋 Excel target 欄位混入 PDF template，這個邊界是否太嚴或剛好？
4. `renderer_registry` 把 `pdf_overlay` 登錄成 `schema_only`，是否是進 renderer 前最安全的狀態？
5. 在寫 renderer 前，P1 的 output result envelope 是否必須先做？目前尚未統一。
6. demo edge matrix 尚未完整做：缺 after、未定側照片、多頁照片、table overflow、PDF 多頁。這是否要排在 renderer 前？
7. AcroForm 填表應該現在就納入 `kind` 設計，還是等 overlay renderer 第一版後再加？

## 我目前的判斷

目前可以給你校準，但還不建議直接大步寫完整 renderer。

我傾向下一步先做：

1. output result envelope v1。
2. demo edge matrix。
3. PDF overlay renderer 的最小垂直切片。

請你幫忙判斷這個順序是否正確，以及有沒有漏掉會讓公司級產品踩雷的 P0/P1。
