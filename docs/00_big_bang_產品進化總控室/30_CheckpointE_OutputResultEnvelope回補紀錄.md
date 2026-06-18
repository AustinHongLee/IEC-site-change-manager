# Checkpoint E output_result.v1 envelope 回補紀錄

日期：2026-06-17

## 來源

`29_Opus校準結果_CheckpointE.md` 建議在寫 `pdf_overlay` renderer 前，先統一 output result envelope。原因是新 renderer 一出生就應該符合共同契約，避免後續三套輸出結果各長各的 JSON。

## 契約

新增 `control/output_result.py`：

```json
{
  "result_schema_version": "output_result.v1",
  "ok": true,
  "outputs": [
    {
      "kind": "xlsx_template",
      "path": "output/demo.xlsx",
      "role": "primary",
      "label": "Excel template workbook",
      "optional": false,
      "exists": true
    }
  ],
  "issues": [],
  "capabilities": {},
  "steps": [
    {
      "key": "xlsx_template_render",
      "ok": true,
      "label": "Render xlsx_template workbook",
      "detail": ""
    }
  ]
}
```

## 設計取捨

- 不移除既有 renderer 詳細欄位。
- `path`、`post_validation`、`pdf_conversion`、`pdf_validation` 等舊欄位保留。
- envelope 是 UI / 批次 / AI 接管優先讀取的共同表層。
- renderer-specific debug 與 validation 細節仍可留在各 renderer 自己的欄位。

## 接入範圍

### `control/workbook_pdf_converter.py`

- `convert_workbook_to_pdf()` 成功與失敗都會回 `output_result.v1`。
- 成功時 `outputs` 包含 `kind=pdf`。
- `capabilities.libreoffice` 保留 LibreOffice 探測結果。
- `steps` 包含 `libreoffice_convert` 與 `pdf_validation`。

### `control/renderer_registry.py`

- `xlsx_template` render result 補 envelope。
- `xlsx_com` unavailable / not ready 補 envelope。
- `pdf_overlay schema_only` 補 envelope。
- unknown renderer 補 envelope。

### `tools/render_xlsx_template.py`

- `--json` 會輸出 envelope。
- 若有 `--pdf-output`，PDF 成功會追加 `kind=pdf` output；PDF 失敗會在 `steps` 補 `workbook_pdf_conversion` 並保留 issue。

### `tools/export_site_statistics.py`

- `--json` 會輸出 envelope。
- 現場統計單 workbook 為 `kind=site_statistics_xlsx`。
- PDF 後處理採同一套追加策略。

## 測試

- `tests/test_output_result.py`
- `tests/test_workbook_pdf_converter.py`
- `tests/test_render_xlsx_template_tool.py`
- `tests/test_export_site_statistics_tool.py`
- `tests/test_renderer_registry.py`
- `tests/test_demo_smoke.py`
- `tests/test_import_guard.py`

## 尚未做

- 尚未把所有 GUI 事件都改成只讀 envelope。
- 尚未為 output envelope 建立 JSON schema 檔。
- 尚未把 `demo_smoke` 最外層 result 完全 envelope 化；目前其子輸出已具備 envelope。
