# Opus 校準請求 Checkpoint B：材料價目與補價流程

日期：2026-06-16
狀態：Codex 已完成第一輪落地，建議 Opus 進場做產品級校準。

---

## 1. 這次為什麼需要 Opus 校準

本輪已碰到公司級工具的高風險財務鏈：

`材料價目表 → 材料明細拍照 → 未定價提示 → 補價 → 重配未定價材料 → 請款金額`

這條鏈一旦 UX 或資料規則設計錯，風險不是單純 bug，而是：

- 使用者以為材料已入價，其實仍未請款。
- 補價後回沖已請款資料，造成歷史請款依據變動。
- 手動調整價被價目表覆蓋。
- AI 產出的價目骨架污染專案價目表。
- UI 看得懂但流程仍不符合內業/會計實際操作。

因此建議 Opus 在下一個功能擴張前先校準。

---

## 2. Codex 已落地內容

### 2.1 材料受控詞彙

- 新增 `control/material_constants.py`
- 權威來源仍是 `control/wizard_data.json`
- 統一零件類型、尺寸、SCH、材質、材質 alias、預設單位
- 舊資料如 `白鐵` / `SS` / `黑鐵` / `CS` 會正規化成完整材質字串

### 2.2 價目表 seed 驗證與安全匯入

- 新增 `control/material_pricebook_validation.py`
- 新增 `control/material_pricebook_importer.py`
- `tools/validate_pricebook.py` 與 `tools/import_pricebook_seed.py` 已變成薄外殼
- `material_pricebook_seed.json` 目前 442 筆，驗證結果為 `WARNING 0 / ERROR 0`
- 匯入規則：
  - 預設 dry-run
  - UI/CLI 都會先顯示既有筆數、seed 筆數、將新增、已存在略過
  - 寫入前需二次確認
  - 同一 `(零件類型, 尺寸, SCH, 材質)` 已存在就略過，不覆蓋既有價目

### 2.3 空白單價與未定價狀態

- 價目表 item 允許 `單價=""`
- 有價目骨架但單價空白時，材料明細標記：
  - `單價來源=missing_price`
  - `金額來源=missing_price`
  - `配價狀態=missing_price`
- UI 顯示「未定價」，不顯示 0 元
- 價目表找不到材料時仍是 `missing_pricebook` / 「未配價」

### 2.4 價目表 UI 補價流程

- 材料價目表面板新增：
  - `匯入骨架`
  - `只看未定價`
  - `套用補價`
- 空白單價列在表格中顯示「未定價」並以警示色標示
- 雙擊「未定價」欄位時，提示字不會寫回資料層

### 2.5 補價後安全重配

- 新增 `control/material_repricing.py`
- 補價後可只重配既有材料明細中的未定價/未配價列
- 安全規則：
  - 已請款鎖定狀態略過
  - 手動價略過
  - 已有單價略過
  - 只更新未定價/未配價材料
- UI 套用前會顯示：
  - 材料總筆數
  - 待重配未定價
  - 可套用補價
  - 仍未填單價
  - 仍無價目
  - 已請款略過
  - 手動價略過

---

## 3. 驗證結果

已跑：

```powershell
python -m pytest -s tests
python control\main.py --health-check
python tools\validate_pricebook.py material_pricebook_seed.json
python tools\import_pricebook_seed.py material_pricebook_seed.json
git diff --check
```

結果：

- 測試：`197 passed`
- 健康檢查：`healthy`
- 既有 warning：2 個 attachments 子資料夾尚未寫入 records
  - `20250820/55_2a2`
  - `20260112/0547_AG`
- seed 驗證：`WARNING 0 / ERROR 0`
- seed dry-run：既有 0 筆、seed 442 筆、將新增 442 筆、略過 0 筆
- `git diff --check`：無 whitespace error，只有 Windows LF/CRLF 提醒

---

## 4. 請 Opus 校準的問題

### 4.1 產品流程

1. 「材料價目表」面板目前承擔匯入、補價、套用補價三件事，是否會讓非工程使用者混淆？
2. `只看未定價` + `套用補價` 的操作順序是否足夠直覺？
3. 是否需要在「紀錄管理」或「請款追蹤」面板也顯示未定價材料總數，避免使用者忘記補價？
4. 補價完成後是否應該自動提示哪些修改單金額改變，還是目前只顯示總數即可？

### 4.2 財務安全

1. 已請款鎖定、手動價略過、既有單價略過，這三條安全邊界是否足夠？
2. `missing_pricebook → missing_price → matched` 的狀態流是否符合會計/內業語意？
3. 補價後重配未定價材料，是否需要 append-only audit？
4. 價目表變更 history 目前記錄改價，但重配材料明細本身是否也要記錄 old→new？

### 4.3 UI/UX

1. 空白單價在價目表顯示「未定價」是否清楚，還是應改成更會計語言的詞？
2. 「套用補價」這個按鈕命名是否準確？
3. 大量 442 筆 seed 匯入後，價目表 UI 是否需要更強的篩選條件，例如零件類型、材質、尺寸段？
4. 是否要提供批次填價或貼上 Excel 價格表的入口？

### 4.4 下一步排序

請 Opus 判斷下一階段優先順序：

1. 補材料價目 UX：批次填價、匯入 Excel 價格表、未定價總覽
2. 請款批次 UX：批次明細、狀態同步規則、請款匯出
3. 財務 audit：材料補價與重配價 append-only 稽核
4. 單一 exe / 啟動守門打包路線

---

## 5. Codex 初步判斷

我認為目前已到 Opus 該進場的 checkpoint，原因是：

- 材料系統已從資料模型走到真實操作流程。
- 下一步若直接做請款批次同步，會把材料補價結果帶入更高風險的財務狀態。
- 現在讓 Opus 校準，成本低；等請款批次與匯出都做完再改 UX，返工會大。

Codex 建議：先讓 Opus 校準本文件，再決定下一波進入「材料補價 UX」或「請款批次 UX」。
