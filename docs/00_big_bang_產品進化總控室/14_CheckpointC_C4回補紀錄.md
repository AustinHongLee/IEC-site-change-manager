# Checkpoint C C4 回補紀錄

日期：2026-06-17

## 回補項目

Opus Checkpoint C 指出 xlsx template 使用 cell anchor 與像素尺寸貼圖，但沒有檢查圖片、文字與表格區域是否互相重疊或超出工作表邊界。

## 採納修法

- `xlsx_template_renderer.py` 新增 `validate_xlsx_template_layout()`。
- render 前會建立每個 mapping 的 Excel cell 區域：
  - `text`：目標 cell 佔 1 格。
  - `image`：若有 `size_cells: [cols, rows]`，使用該格數；未設定時保守視為 1 格。
  - `table`：用 `start_cell`、`max_rows / rows_per_page`、`columns` 算保留區。
- render 前檢查：
  - 區域互相重疊：`layout_overlap` error。
  - 區域超出 Excel 邊界：`layout_out_of_bounds` error。
  - 缺少 cell / anchor / start_cell 或 `size_cells` 無效：layout error。
- 若 layout validation 失敗，renderer 不產出 workbook。

## 驗證

- focused tests：xlsx renderer / render CLI 共 11 tests passed。
- 真資料合法模板 smoke：`layout_validation.ok=true`、`post_validation.ok=true`、regions=4。
- 故意重疊模板 smoke：text `A1` 與 image `A1:B2` 重疊，CLI exit code 1，未產生輸出檔。

## 限制

- 圖片未宣告 `size_cells` 時，目前只視為 anchor cell 佔 1 格。模板作者若要精準防碰撞，應明確設定 `size_cells`。
- 這次只回補 xlsx template。PDF overlay 的座標 overlap/越界偵測需在 PDF renderer 落地時另做。

## 後續

Checkpoint C 剩餘項目：

- C5：舊 COM 輸出路徑降級與 canonical 接軌。
- C6：field-path catalog 中照片路徑表示法收斂。
