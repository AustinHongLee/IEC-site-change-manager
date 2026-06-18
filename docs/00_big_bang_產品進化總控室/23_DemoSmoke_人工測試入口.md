# Demo Smoke 人工測試入口

日期：2026-06-17

## 目的

目前專案已有 CanonicalReport、現場統計單、xlsx_template、非 COM PDF 後處理與輸出能力檢查。為了讓使用者、AI、或未來打包流程不用靠正式專案資料冒險測試，新增一套可重跑 demo smoke。

## 指令

```powershell
python tools/run_demo_output_smoke.py --output staging/demo_output --overwrite
```

輸出 JSON：

```powershell
python tools/run_demo_output_smoke.py --output staging/demo_output --overwrite --json
```

嘗試 PDF：

```powershell
python tools/run_demo_output_smoke.py --output staging/demo_output --overwrite --pdf
```

若要把 PDF 轉檔視為必須成功：

```powershell
python tools/run_demo_output_smoke.py --output staging/demo_output --overwrite --require-pdf
```

## 產物

預設會產在 `staging/demo_output/`，此資料夾已被 `.gitignore` 排除。

| 檔案 | 用途 |
|---|---|
| `attachments/20260617/0547_AG/` | demo 現場附件資料夾 |
| `records/demo_canonical_report_set.json` | CanonicalReportSet 範例 |
| `templates/demo_field_report.template.json` | xlsx_template 範例 |
| `output/demo_field_report.xlsx` | 範例模板輸出 |
| `output/demo_site_statistics.xlsx` | 現場統計單輸出 |
| `output/demo_field_report.pdf` | 裝好 LibreOffice 且加 `--pdf` 時產生 |

## 人工檢查

1. 開啟 `output/demo_field_report.xlsx`。
2. 確認 `現場修改單` 工作表內：
   - A1 是 `0547_AG`。
   - C1 是 `0547`。
   - before/after 圖片都有貼入。
   - 焊口表有 2 筆。
   - 材料表有 2 筆。
3. 開啟 `output/demo_site_statistics.xlsx`。
4. 確認有：
   - `總覽`
   - `修改單清單`
   - `焊口統計`
   - `照片索引`
   - `照片表`
   - `用料統計`
   - `問題清單`
5. 若有安裝 LibreOffice，執行 `--pdf` 後確認 `output/demo_field_report.pdf` 可開啟。

## 安全規則

- demo 工具只會覆寫帶有 `.iec_demo_project` marker 的資料夾。
- 若指定到非 demo 資料夾，就算加 `--overwrite` 也會拒絕覆寫。
- 此工具不寫入正式專案的 `records.json`、正式 `attachments/` 或正式 `output/`。

## 驗證

- `tests/test_demo_smoke.py`
- `tests/test_run_demo_output_smoke_tool.py`
- `tests/test_import_guard.py`

目前 smoke 已納入 full test，並會驗證：

- demo 專案可建立。
- xlsx_template 輸出成功且 post validation 通過。
- 現場統計單可產出。
- CLI JSON 可解析。
- 非 demo 資料夾不會被覆寫。
