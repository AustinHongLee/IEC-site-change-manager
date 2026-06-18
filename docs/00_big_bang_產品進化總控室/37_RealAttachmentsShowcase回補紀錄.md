# Real attachments showcase 回補紀錄

日期：2026-06-17

## 目的

使用 `attachments/` 內的真實測試資料，不靠 demo 假資料，展示目前資料核心已可串起：

- attachments scan
- `CanonicalReportSet`
- 現場統計單 Excel
- PDF overlay
- table `overflow=new_page`
- PNG 目視檢查

## 新增入口

```powershell
python .\tools\run_real_attachments_showcase.py `
  --output .\staging\real_attachments_showcase_cli `
  --overwrite `
  --png `
  --json
```

安全邊界：

- 輸出資料夾會寫入 `.iec_real_attachments_showcase` marker。
- `--overwrite` 只允許覆寫有 marker 的 showcase 資料夾。
- 不會改動原始 `attachments/`。

## 新增程式

### `control/real_attachments_showcase.py`

新增 `run_real_attachments_showcase()`：

- 收斂 `attachments/` 成 `report.v1`。
- 輸出 `records/real_canonical_report_set.json`。
- 輸出 `output/real_site_statistics.xlsx`。
- 建立 `templates/real_pdf_overlay.template.json`。
- 逐張 report 產 `real_pdf_overlay_{folder}.pdf`。
- 可選 `--png` 轉成 PNG。

### `tools/run_real_attachments_showcase.py`

CLI 包裝，支援：

- `--project-root`
- `--attachments-root`
- `--output`
- `--overwrite`
- `--no-pdf`
- `--png`
- `--json`

## 真資料展示結果

以目前 `attachments/` 兩包測試資料實跑：

- report_count: 2
- weld_count: 8
- material_row_count: 3
- photo_count: 6
- before_photo_count: 3
- after_photo_count: 3

輸出：

- `staging/real_attachments_showcase_cli/records/real_canonical_report_set.json`
- `staging/real_attachments_showcase_cli/output/real_site_statistics.xlsx`
- `staging/real_attachments_showcase_cli/output/real_pdf_overlay_55_2a2.pdf`
- `staging/real_attachments_showcase_cli/output/real_pdf_overlay_0547_AG.pdf`
- `staging/real_attachments_showcase_cli/output/real_photo_grid_55_2a2.pdf`
- `staging/real_attachments_showcase_cli/output/real_photo_grid_0547_AG.pdf`

觀察：

- `55_2a2` 有 before/after、1 口焊口、附件 PDF；沒有材料資料，因此 PDF 表格只有表頭並回 `empty_table` warning。
- `0547_AG` 有 7 口焊口、3 筆材料、4 張照片；因 note 仍是樣板文字，`CanonicalReportSet.issues` 會列出 `note`。
- `0547_AG` PDF 產 2 頁，示範 table `overflow=new_page`。

## 測試

新增：

- `tests/test_run_real_attachments_showcase_tool.py`

已跑 focused：

```powershell
python -m pytest -s `
  .\tests\test_run_real_attachments_showcase_tool.py `
  .\tests\test_canonical_report.py `
  .\tests\test_site_statistics_exporter.py `
  .\tests\test_pdf_overlay_renderer.py `
  .\tests\test_template_dry_run.py
```

結果：

- 26 passed

## 下一步

PDF 外觀暫時不是重點；現在已證明真資料可以被穩定收進核心模型。

已於 `38_PhotoGridTableImageCell回補紀錄.md` 回補：

- 多頁照片 grid：建在 `table` primitive 上，不新增第 4 種 primitive。

下一步應優先做：

- GUI 入口：從健康/輸出頁提供「產生真資料展示」或「用目前 attachments 產統計單」。
- CJK 字型嵌入：正式 PDF 對外交付前處理。
