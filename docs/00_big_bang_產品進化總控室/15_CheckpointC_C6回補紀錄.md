# Checkpoint C C6 回補紀錄：照片 field-path 表示收斂

日期：2026-06-17

## 問題

Opus Checkpoint C 指出，照片欄位同時出現 `photos.before[0..n]` 與 `photos.before[*].path` 兩種集合寫法。這會讓模板作者與 AI 不知道哪一種才是正式契約，也會增加 coverage 與 validation 的判斷分歧。

## 決策

- 正式 field-path catalog 一律使用 `[*]` 作為集合表示。
- `photos.before[*]` / `photos.after[*]` 是照片集合根路徑。
- `photos.before[*].path`、`photos.after[*].path` 等 leaf path 繼續保留。
- `[0..n]` 不再由 `list-fields` 輸出，只作為舊模板相容解析。
- `[0]`、`[1]` 這類定值索引繼續支援，供 text/image 單張照片使用。

## 實作

- `control/canonical_fields.py`：移除 `photos.before[0..n]` / `photos.after[0..n]`，新增 `photos.before[*]` / `photos.after[*]`。
- `control/template_mapping.py`：驗證器可把 `[0..n]` 正規化成 `[*]`，並修正 bracket 內含 `.` 時的 field-path 切割。
- `control/template_mapping.py`：table 欄位拼接支援 `photos.before[*]` 這種已帶集合 selector 的 source，避免產生 `photos.before[*][*].path`。
- `control/template_dry_run.py`：coverage 分析把 `[*]` 集合根視為 collection root，不列為未映射孤兒資料。

## 驗證

- `test_canonical_report.py` 與 `test_list_canonical_fields_tool.py` 鎖定 `list-fields` 不再輸出 `[0..n]`。
- `test_template_mapping.py` 確認數字索引、舊 `[0..n]` 相容，以及 `photos.before[*]` 作為 table source 皆可驗證。
- `test_template_dry_run.py` 確認 `photos.before[*]` / `photos.after[*]` 不會被錯誤列為 unmapped data。

## 後續

這次只處理 C6。Checkpoint C 仍剩 C5：舊 Excel COM output 需逐步降級為 optional renderer，並讓核心輸出路線走 CanonicalReport。
