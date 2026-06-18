# Checkpoint C C1 回補紀錄

日期：2026-06-17

## 回補項目

Opus Checkpoint C 指出 `xlsx_template_renderer` 的表格溢出只在 dry-run 偵測，renderer 仍會把所有列寫進 Excel，可能覆蓋表格下方既有版面。

## 採納修法

- `table` mapping 必須設定 `max_rows` 或 `rows_per_page`，否則 `validate_template` 直接失敗。
- dry-run 偵測到 `table_overflow` 時，severity 由 warning 升級為 error，整份 dry-run `ok=false`。
- renderer 在 dry-run 不通過時不寫出 workbook，避免留下已覆蓋版面的錯檔。
- renderer 的 `_render_table` 也讀取列數上限，作為第二道保險，避免未來繞過 dry-run 時寫過界。

## 驗證

- focused tests：template mapping / validate template / dry-run / xlsx renderer / CLI 共 19 tests passed。
- 真資料合法模板 smoke：`55_2a2` 可輸出文字、焊口表格與 1 張圖片。
- 故意溢出模板 smoke：CLI exit code 1，未產生輸出檔。

## 後續

C1 已回補。Checkpoint C 其餘項目仍屬後續工作：

- C2：輸出後校驗。
- C3：孤兒資料報告。
- C4：圖片與表格區域重疊/越界偵測。
- C5：舊 COM 輸出路徑降級與 canonical 接軌。
- C6：field-path catalog 中照片路徑表示法收斂。
