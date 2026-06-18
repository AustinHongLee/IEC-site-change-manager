# Checkpoint E demo edge matrix 回補紀錄

日期：2026-06-17

## 來源

`29_Opus校準結果_CheckpointE.md` 建議在寫 `pdf_overlay` renderer 前先建立 demo edge matrix。目的不是產正式輸出，而是讓 renderer 第一版就有壞資料測試床。

## 新增入口

```powershell
python .\tools\run_demo_output_smoke.py --output .\staging\demo_edge_matrix --overwrite --edge-matrix --json
```

安全邊界沿用 demo smoke：

- 會寫入 `.iec_demo_project` marker。
- `--overwrite` 只允許覆寫有 marker 的 demo 資料夾。
- 不會覆寫正式專案資料夾。

## Edge Cases

| folder | 用途 | 預期 |
|---|---|---|
| `0547_AG` | 正常完整資料 | dry-run 可通過 |
| `0601_NO_AFTER` | 缺 after 照片 | 抓到 `missing_image_value` |
| `0602_MATERIAL_OVERFLOW` | 材料列超過 template 預留 | 抓到 `table_overflow` |
| `0603_MANY_PHOTOS` | before 照片數超過照片表預留 | 抓到 `table_overflow` |
| `0604_MULTI_PAGE_PDF` | 附件 PDF 兩頁 | `attachment_pdf.pages == 2` |

## 產出

- `records/edge_canonical_report_set.json`
- `templates/edge_matrix.template.json`
- `templates/edge_pdf_overlay.template.json`
- `templates/edge_pdf_overlay_rotated.template.json`
- `templates/rotated_vendor_form.pdf`

`edge_matrix.template.json` 使用 `xlsx_template` kind，但目前只做 dry-run，不產 workbook。這讓 renderer 測試床先驗資料與 template 契合度，不綁定某個 renderer。

`edge_pdf_overlay_rotated.template.json` 使用同一組 report mapping，但 base PDF 指向 `/Rotate 90` 的 `rotated_vendor_form.pdf`，用來檢查 renderer 會先把 PDF rotation 轉入 page content 再 overlay。

## 實作

### `control/demo_smoke.py`

- 新增 `run_demo_edge_matrix()`。
- 新增 `build_demo_edge_matrix_template()`。
- 新增多組 edge attachment writer。
- 用 `dry_run_template_for_report()` 檢查每個 case 是否出現預期 issue code。

### `tools/run_demo_output_smoke.py`

- 新增 `--edge-matrix`。

## 測試

- `tests/test_demo_smoke.py`
- `tests/test_run_demo_output_smoke_tool.py`

## 後續狀態更新

Checkpoint E 後已新增 `pdf_overlay` minimal renderer，並用 demo template 產出 `staging/demo_output/output/demo_pdf_overlay.pdf`，再以 Poppler 轉 PNG 做目視檢查。

2026-06-17 補上 `/Rotate` fixture：

```powershell
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

已目視檢查 `staging/demo_edge_matrix/output/edge_pdf_overlay_rotated_page.png`：旋轉底圖轉正後，文字、before/after 圖片與材料表皆落在預期位置。

## 尚未做

- 尚未把 edge matrix 的壞資料逐一接成 pdf_overlay renderer 的視覺 regression。
- 尚未把每個壞資料 case 都建立真實視覺 render 的像素或 PDF 頁面檢查。
