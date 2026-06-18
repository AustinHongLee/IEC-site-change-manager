# Site Output Runner 共用流程回補紀錄

日期：2026-06-18

## 目的

上一階段正式建立 `site_output_center` 後，`site_output_center.py` 與 `real_attachments_showcase.py` 仍各自保有一份幾乎相同的輸出流程。

本階段將共同流程抽到 `control/site_output_runner.py`，降低後續修改 CanonicalReport 輸出、PDF overlay、統計 Excel 時的雙邊維護風險。

## 新增共用模組

### `control/site_output_runner.py`

新增：

```python
SiteOutputBundleConfig
run_site_output_bundle(...)
```

共用 runner 負責：

- 建立 marker 保護的輸出根目錄
- 收集 `CanonicalReportSet`
- 寫出 report set JSON
- 產生現場統計單 Excel
- 寫出 PDF overlay template 與 base PDF
- 依勾選內容產 summary PDF / photo grid PDF
- 回傳統一 summary result

## 保留的產品入口

### `control/site_output_center.py`

保留正式入口：

```python
run_site_output_center(...)
```

正式輸出命名維持不變：

- `.iec_site_output_center`
- `canonical_report_set.json`
- `site_statistics.xlsx`
- `site_summary_{folder}.pdf`
- `site_photo_grid_{folder}.pdf`
- `output_center_summary.json`

### `control/real_attachments_showcase.py`

保留 showcase/demo 入口：

```python
run_real_attachments_showcase(...)
```

既有展示輸出命名維持不變：

- `.iec_real_attachments_showcase`
- `real_canonical_report_set.json`
- `real_site_statistics.xlsx`
- `real_pdf_overlay_{folder}.pdf`
- `real_photo_grid_{folder}.pdf`
- `showcase_summary.json`

## 重要邊界

- `site_output_runner.py` 不決定產品命名，只吃 `SiteOutputBundleConfig`。
- 正式輸出中心與 showcase 仍可各自擁有不同 template。
- 覆寫保護訊息維持原有語意，避免 CLI 測試與使用者提示被改掉。
- GUI 仍呼叫 `run_site_output_center(...)`，不直接碰共用 runner。

## 驗證

已跑 focused：

```powershell
python -m pytest -s `
  .\tests\test_run_site_output_center_tool.py `
  .\tests\test_run_real_attachments_showcase_tool.py `
  .\tests\test_billing_panel_logic.py
```

結果：

- 38 passed

已跑完整測試：

```powershell
python -m pytest -s .\tests
```

結果：

- 328 passed

已跑真資料 formal CLI smoke：

```powershell
python .\tools\run_site_output_center.py `
  --output .\staging\site_output_center_cli `
  --overwrite `
  --include 20260112/0547_AG `
  --json
```

結果：

- `ok`: true
- `report_count`: 1
- `output/site_statistics.xlsx`
- `output/site_summary_0547_AG.pdf`
- `output/site_photo_grid_0547_AG.pdf`
- 既有資料 issue：`0547_AG` 缺少現場 note 或仍是樣板文字

## 下一步

- 若穩定，再考慮把 GUI 內部 `_showcase_*` helper 逐步改名為 `_output_center_*`，並保留 alias 減少測試衝擊。
