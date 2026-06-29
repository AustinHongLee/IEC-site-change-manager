# Task 7 契約：精靈輸出閉環（照片/PDF/材料 + gating + 匯出，**大步版**，給 Codex）

> **前置**：讀 `執行指導書_新修改單系統_v1.md` §C/§D/§E，以及四個模組 API：`change_order` / `change_order_builder` / `change_order_store` / `change_order_wizard`（Task 5 那支）。
> **這是「大步版」**：把第一刀刻意省的一次補齊，別再切小。但紀律不變：`git diff --stat` 先給人看、一任務一 commit、守禁區、做完 STOP。

---

## 目標

把 Task 5 的新精靈從「只能加焊口 + 存 JSON」補成**完整出單閉環**：加照片/PDF/材料 → 完整度把關 → 呼叫匯出層真的搬檔出單。**只動新精靈那支（`control/change_order_wizard.py`）**；舊 `wizard.py` / `gui.py` 一樣不准碰。

---

## 要做的事

1. **照片輸入**：加 before / after 照片（檔案選擇器取路徑），可多張，列出、可移除。
2. **圖面 PDF 輸入**：檔案選擇器選 PDF。
3. **材料輸入**：簡單表單（component / size / sch / material / qty / unit / remark）加入清單，可移除。
4. **replay 一致**：沿用既有「請求清單重放」模式——把照片 / PDF / 材料 / 原因也納入重放，任何變更都用全新 builder 重建 `co`（`add_photo` / `set_drawing_pdf` / `add_material` / `set_reason`）。
5. **完整度 gating**：即時顯示 `validate` / `compute_status`。規則：**「完整」＝ before + after + 圖面PDF 齊**（走 `builder.validate` 的硬底）。
   - **「正式建立」：status 非「完整」時擋下**（或明確提示缺什麼）。
   - **「存草稿」一律允許**（待補也能存）。
6. **改用匯出層出單**：存檔改呼叫 `change_order_store.export_change_order(co, attachments_root)`——`finalize_id` 之後 export，真的把照片/PDF 複製進 `{root}/{id}/`、寫 record（相對檔名）。`attachments_root` 注入（預設一個合理路徑）。
   - 存草稿與正式都走 export（差別只在 gating 准不准按「正式」）；export 的缺檔 / overwrite 行為已驗，直接用。

---

## 注入（維持可測）

- 對話框 `__init__(self, builder=None, *, attachments_root=None)`；測試注入 fixture-backed builder + temp `attachments_root`。

---

## 硬禁區（絕對不碰）

- 不碰 `wizard.py` / `gui.py` / renderers / 任何**舊**既有檔。
  （**可以**改 `change_order_wizard.py` 與其 smoke test——那是我們自己的新精靈，預期會動。）
- 不在 UI 重寫匯出 / 複製邏輯（用 `change_order_store`）、不重寫焊口編號（用 `builder`）。
- 不接 `gui.py` 選單（那是 Task 8）。
- 不碰那 15 個既有紅的 PDF / 輸出測試。

---

## 驗收標準（offscreen 煙霧測，擴充既有那支）

- 注入 fixture-backed builder + temp `attachments_root`，程式化驅動：
  - 加既有焊口（沿用）→ code 對（如 `2b`）。
  - 加 before + after 照片（指向 temp 假檔）+ PDF + 一筆材料。
  - `compute_status`：before + after + pdf 齊 → **完整**；少一個 → **待補**，且「正式建立」被擋。
  - 觸發出單 → **斷言 `export_change_order` 真的跑了**：`{root}/{id}/` 生出、`before_1.*` / `after_1.*` / `drawing.pdf` 複製進去、`change_order.json` 內檔案引用是**相對名**、材料在 record 裡、`ChangeOrder.load_json` 讀回對。
  - series 正規化仍成立（088→88、id `88_…`）。
- 既有 15 紅維持同名；**舊 `wizard.py` / `gui.py` mtime 不變（沒碰）**。
- offscreen 可建構。

---

## 交付格式

1. 先貼 `git diff --stat` ＋ 改動/新增大綱，等確認（注意這次會**修改 `change_order_wizard.py`**，屬預期，不是禁區）。
2. 一個 commit：`feat(wizard2): add photos/materials input, completeness gating, store export (Task 7)`。
3. 回報：測試結果、確認既有 15 紅未變、**確認只動了新精靈那支 + 其測試**（沒碰舊檔）、對 **Task 8**（接 `gui.py` 選單）的銜接建議。
4. git / commit 由你（Codex）原生執行；**diff-first 給人看過再 commit**。然後 STOP。

---

*權威型別/服務以 `change_order` / `change_order_builder` / `change_order_store` 為準；UI 仍是薄殼，邏輯不重寫。Task 8 才會碰 `gui.py`（屆時回到嚴格 review）。*
