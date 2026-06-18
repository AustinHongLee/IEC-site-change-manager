# Site Output Center 正式命名回補紀錄

日期：2026-06-18

## 目的

前期為了快速驗證真實 attachments 資料，輸出管線命名為 `real_attachments_showcase`。

本階段將正式產品入口抽出為 `site_output_center`，避免公司使用者與後續 AI 在正式流程中看到 showcase/demo 語意。

## 新增正式模組

### `control/site_output_center.py`

新增正式 API：

```python
run_site_output_center(...)
```

輸出採正式命名：

- `records/canonical_report_set.json`
- `output/site_statistics.xlsx`
- `templates/site_summary_pdf.template.json`
- `templates/site_photo_grid.template.json`
- `templates/site_output_base.pdf`
- `output_center_summary.json`
- `output/site_summary_{folder}.pdf`
- `output/site_photo_grid_{folder}.pdf`

安全 marker：

```text
.iec_site_output_center
```

既有非 output-center 資料夾不允許覆寫。

## 新增正式 CLI

### `tools/run_site_output_center.py`

參數沿用前一階段的輸出中心能力：

- `--include DATE/FOLDER`
- `--no-statistics`
- `--no-summary-pdf`
- `--no-photo-grid-pdf`
- `--no-pdf`
- `--png`
- `--json`

舊入口 `tools/run_real_attachments_showcase.py` 保留，作為 demo/回歸測試入口。

## GUI 改接正式入口

### `control/gui_panels.py`

紀錄管理頁 `輸出中心` 現在呼叫：

```python
run_site_output_center(...)
```

預設輸出資料夾改為：

```text
staging/site_output_center_gui
```

結果對話框同時相容舊 result 的 `showcase` 與新 result 的 `output_center` key。

## 測試

新增：

- `tests/test_run_site_output_center_tool.py`

已跑 focused：

```powershell
python -m pytest -s `
  .\tests\test_run_site_output_center_tool.py `
  .\tests\test_run_real_attachments_showcase_tool.py `
  .\tests\test_billing_panel_logic.py
```

結果：

- 38 passed

## 實資料驗證

正式 CLI 實跑：

```powershell
python .\tools\run_site_output_center.py `
  --output .\staging\site_output_center_cli `
  --overwrite `
  --include 20260112/0547_AG `
  --json
```

結果：

- `output_center`: `staging/site_output_center_cli`
- `report_count`: 1
- `output/site_statistics.xlsx`
- `output/site_summary_0547_AG.pdf`
- `output/site_photo_grid_0547_AG.pdf`

## 下一步

正式命名已建立，但仍有兩個技術債：

- `real_attachments_showcase.py` 與 `site_output_center.py` 目前邏輯相近，之後可抽共用 renderer runner，降低維護重複。
- GUI helper 函式仍保留 `_showcase_*` 內部命名，之後可逐步改成 `_output_center_*`，測試保留 alias 避免一次重構過大。
