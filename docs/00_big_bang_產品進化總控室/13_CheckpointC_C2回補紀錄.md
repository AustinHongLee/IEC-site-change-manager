# Checkpoint C C2 回補紀錄

日期：2026-06-17

## 回補項目

Opus Checkpoint C 指出 `xlsx_template_renderer` 只有 dry-run 前測，缺少輸出後重新讀檔校驗。若 renderer 寫入失敗、圖片未嵌入、或表格值跑掉，原本無法在 render result 中被抓出。

## 採納修法

- `xlsx_template_renderer.py` 新增 `validate_rendered_xlsx_workbook()`。
- renderer 儲存 workbook 後會重新 `load_workbook()`，確認：
  - `text`：目標 cell 值與 CanonicalReport 來源值一致。
  - `image`：存在的圖片確實嵌在指定 anchor；缺圖降級時 placeholder 正確。
  - `table`：每個輸出列與欄位值都與來源資料一致。
- render result 新增 `post_validation`，含 `ok`、`checked` 與 `issues`。
- 若輸出後校驗發現 error，render result 會轉為 `ok=false`，並把 post-validation issue 併入總 issue 清單。

## 驗證

- focused tests：xlsx renderer / render CLI 共 8 tests passed。
- 後測失敗回歸：產檔後故意改壞 text cell 與 table cell，`validate_rendered_xlsx_workbook()` 可抓出 `post_validation_text_mismatch` 與 `post_validation_table_mismatch`。
- 真資料 smoke：用目前專案第一筆資料輸出 xlsx，`post_validation.ok=true`，確認 text=2、image=1、table=1、rows=1。

## 後續

C2 的 xlsx 路線已回補。Checkpoint C 剩餘項目：

- C4：圖片與表格區域重疊/越界偵測。
- C5：舊 COM 輸出路徑降級與 canonical 接軌。
- C6：field-path catalog 中照片路徑表示法收斂。
