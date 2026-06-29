# Task 9 契約：新精靈 UI 改皮 — 主題 + 全中文 + 分頁排版（小螢幕可用）+ 使用導引（給 Codex）

> **前置**：讀 `執行指導書_新修改單系統_v1.md` §C/§D/§E、現有 `control/change_order_wizard.py`、`control/theme.py`（`Colors` / `Fonts` / `set_button_role` / `make_hint_label` / `make_separator` 等）、`tests/test_change_order_wizard_smoke.py`（**你不能弄壞它依賴的 widget 名 / 方法名**）。
> 範圍只在「**那支新精靈的外觀與排版**」，**邏輯一律不動**（builder / store / codec / lookup 不碰）。`git diff` 先給人看、一任務一 commit、做完 STOP。

---

## 為什麼有這張

第一版能跑但「像 dev form」：Qt 預設白板、英文 dict-key 當標籤、英文驗證訊息、單頁太長小螢幕難用。**這張只修表面**，讓它像產品、且小螢幕能操作。**功能 / 接線一律不准改。**

---

## 要做的事

### 1. 套既有主題
- `from theme import Colors, Fonts, set_button_role`（以及 `make_hint_label`、`make_separator` 等可用的），讓對話框跟主程式同一套深色藍視覺，不再是預設白板。
- 按鈕分角色：`正式建立` ＝ primary，其餘一般；GroupBox / Label 用 theme 顏色與字級。

### 2. 全中文標籤與訊息
- 欄位標籤全中文：`零件 / 尺寸 / SCH / 材質 / 數量 / 單位 / 備註`；焊口表頭 `焊口碼 / 原始 / 操作 / 規格 / 來源 / 類型`；照片表頭 `角色 / 檔案`；`修改前 / 修改後` 等。
- **驗證訊息中文化**：builder 回的 issue 是英文（`before photo is required`…）。**在 wizard 顯示層用 issue `code` 對應中文**（如 `missing_before_photo → 缺：修改前照片`），**別改 builder**（碼要穩）。狀態列顯示成中文，例：`狀態：待補 ｜ 還缺：修改前照片、修改後照片、圖面 PDF`。

### 3. 排版重做（核心：不能太長、小螢幕要能用）
- **改成分頁 `QTabWidget`**，每頁短：`① 基本資料` ／ `② 焊口` ／ `③ 照片與圖面` ／ `④ 材料`。
- **底部固定一條 action bar**（在分頁外、永遠看得到）：左邊**狀態列**（完整/待補 ＋ 還缺什麼）、右邊 `存草稿`、`正式建立`。
- 對話框預設尺寸**縮小到小螢幕也容得下**（例 ~760×560，**避免固定超高**）；單頁內容多時用 `QScrollArea` 包該頁，**不要**把整個對話框撐很長。

### 4. 使用導引（要明確）
- 每頁頂端一行**提示**（用 `make_hint_label` 或淡色小字）：
  - 焊口頁：`從管制表挑既有焊口改（填 base ＋ 操作），或加全新焊口；編號系統自動算`。
  - 照片頁：`修改前(問題)、修改後(完成)各至少 1 張，並附圖面 PDF`。
- 空清單給佔位提示（`尚未加入焊口` / `尚未加入照片`…）。
- Tab 名稱用 ①②③④ 數字隱含流程順序。

---

## 不准動（重要）

- **不改任何邏輯**：builder / store / codec / lookup / `change_order` 一律不碰。
- **不改 `gui.py`、舊 `wizard.py`、renderers**。
- 不碰那 15 個既有紅。
- **保留 smoke test 依賴的 widget 屬性名與方法名**：`series_edit` / `date_edit` / `reason_edit` / `existing_base_edit` / `existing_op_combo` / `add_existing_request` / `new_*_edit` / `new_op_combo` / `add_new_request` / `weld_table` / `remove_selected_request` / `add_photo_file` / `set_drawing_pdf_file` / `material_*_edit` / `add_material_request` / `create_final` / `save_draft` / `status_label` 等——**可以搬到不同 tab，但不要改名**，否則測試會壞。
  - 若你把 `status_label` 文字格式中文化，**同步更新 smoke test 的字串斷言**（那是我們自己的測試，可改；但 export / 相對名 / gating / 088→88 / 編號那些**核心斷言要保留**）。

---

## 驗收標準

- offscreen smoke **仍綠**（必要時只更新中文化後的字串斷言；核心流程：`088→88`、`2b`/`2c`、`1001`/`1002`、gating 擋、export 真複製、JSON 相對名、材料入 record——**全部要保留**）。
- 既有 15 紅維持同名；`gui.py` / 舊 `wizard.py` 沒動（原生 `git diff --stat` 只該有 `change_order_wizard.py` ＋ 其 test）。
- **視覺 / 小螢幕的最終確認由使用者親眼看**（Opus 沒 PyQt6、跑不了畫面）。

---

## 交付格式

1. 先貼 `git diff --stat` ＋ **新版 UI 結構大綱**（幾個 tab、各放什麼、底部 bar 長怎樣），等確認。
2. 一個 commit：`feat(wizard2): theme, Chinese labels, tabbed compact layout, usage hints (Task 9)`。
3. 回報：測試結果、確認既有 15 紅未變、確認只動新精靈那支 ＋ 其 test、有無改 `status_label` 文字（及對應測試更新）。
4. git / commit 由你（Codex）原生執行；**diff-first 給人看過再 commit**。然後 STOP。

---

*這張是「上妝」：只動 `change_order_wizard.py` 的外觀/排版層，邏輯與接線維持 Task 7 的樣子。完成後使用者會親自開 GUI 看成品。*
