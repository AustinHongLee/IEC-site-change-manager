# Checkpoint C C3 回補紀錄

日期：2026-06-17

## 回補項目

Opus Checkpoint C 指出 dry-run 只有「模板欄位取不到值」的正向檢查，缺少反向檢查：CanonicalReport 中有資料，但模板完全沒有使用到它。

## 採納修法

- `template_dry_run.py` 新增 `coverage` 分析。
- dry-run 結果會列出：
  - `covered_paths`：模板已覆蓋的 canonical field paths。
  - `unmapped_data`：CanonicalReport 有值、但模板未使用的欄位。
  - `unmapped_data_count`：未映射資料欄位數。
- 每個未映射欄位會追加 `info / unmapped_data` issue，不會讓 dry-run 失敗。
- 模板可用 `coverage_ignore` 明確列出不打算輸出的欄位，避免預期中的省略形成噪音。

## 補充修正

- `dry_run_template.py --json` 直接掃目前專案時，stdout 保持純 JSON；app log banner 會被導到 stderr，避免外部 UI 或 AI 工具解析失敗。
- `render_xlsx_template.py --json` 同步採用相同處理。

## 驗證

- focused tests：template dry-run / dry-run CLI 共 9 tests passed。
- 真資料 smoke：只輸出 `report.folder` 的模板可列出反向未映射資料。
  - `55_2a2`：26 個有值欄位未映射。
  - `0547_AG`：33 個有值欄位未映射。

## 後續

C3 已回補。Checkpoint C 剩餘項目：

- C2：輸出後校驗。
- C4：圖片與表格區域重疊/越界偵測。
- C5：舊 COM 輸出路徑降級與 canonical 接軌。
- C6：field-path catalog 中照片路徑表示法收斂。
