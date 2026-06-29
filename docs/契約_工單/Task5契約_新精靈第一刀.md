# Task 5 契約：新精靈第一刀 — 源頭驅動焊口輸入（Qt，給 Codex）

> **前置**：先讀 `執行指導書_新修改單系統_v1.md` §C/§D/§E，以及四個模組的 API：`change_order` / `weld_lookup` / `weld_codec` / `change_order_builder`。
> **這是整個專案第一段 Qt 程式碼，風險最高，所以刻意切到最小。**
> **鐵律**：一任務一 commit、`git diff --stat` 先給人看再 commit、守硬禁區。做完 STOP 回報。

---

## 目標

做一個**全新、獨立**的 Qt 對話框 `control/change_order_wizard.py`，當 `ChangeOrderBuilder` 的**薄殼**。第一刀只做主幹：輸入流水號/日期 → 源頭驅動加焊口（既有/新）→ 即時預覽算好的 code 與規格 → 存出 JSON 記錄。

---

## 邊界與安全（最重要，先讀）

- **舊 `wizard.py` / `gui.py` 一個字都不准改、不准接線。** 新精靈用**獨立入口**：提供 `launch()` 函式 + `if __name__ == "__main__":`，可單獨開。接進現有選單是 Task 6+ 的事。
- Qt 層**薄**：所有焊口 / 編號 / 規格邏輯一律走 `ChangeOrderBuilder`；UI **不自己算** a/b/1000+、**不自己讀表**。
- **依賴注入**：對話框 `__init__(self, builder=None, *, records_root=None)`，`builder` 預設 `ChangeOrderBuilder()`；**測試注入 fixture-backed builder**。

---

## 第一刀要做的事

1. **基本輸入**：流水號、日期（預設今天）、原因 `reason`（選填）。
   - **流水號在這層正規化成 raw（去前導零）** 再餵 `builder.start()`——修掉 id/資料夾飄移的老問題。**builder 本身不動，正規化放 UI。**
2. **源頭驅動加焊口**（取代舊 Step3 盲打）：
   - 既有：輸入 `base` + 選操作（裁切/加長/縮短）→ `add_existing_weld` → 列出 `code`、自動帶出的規格、`spec_source`。
   - 新焊口：選操作 + 填規格（size/sch/material/weld_type）→ `add_new_weld` → 列出 1000+ `code`。
3. **焊口清單一致性（關鍵設計）**：UI 持有使用者的「**焊口請求清單**」（每筆＝既有 `base+op` 或 新 `op+spec`）。**任何新增/移除都用一個全新的 builder 把整串重放一次 → 重建 `co.welds`**，確保 `code` 永遠一致（移掉中間一個不會留錯號）。
4. **預覽**：即時顯示這張 ChangeOrder 的焊口表（code / base / op / 規格 / 來源）。
5. **存草稿**：按鈕 → `compute_status`（此刻沒照片，會是「待補」，**正常允許**）→ 蒐集 `records_root` 既有 id → `finalize_id` → `ChangeOrder.save_json()` 寫到 `{records_root}/{id}/change_order.json`。**只寫這一個 JSON。**

---

## 明確不做（留 Task 6+）

- 照片 / PDF / 材料 / 簽認的輸入與複製。
- 建立完整 attachments 資料夾、搬照片。
- 完整度 gating（第一刀允許存「待補」）。
- single / group 情境（第一刀固定 `normal`）。
- 接進 `gui.py` 選單。

---

## 硬禁區（絕對不碰）

- **純新增**：不改 `wizard.py` / `gui.py` / 任何既有檔（含 `change_order_builder` / `weld_lookup` / `weld_codec` / `change_order`）。
- 不複製照片 / PDF、不搬檔（除了寫那一個 JSON）。
- 不碰那 15 個既有紅的 PDF / 輸出測試。

---

## 驗收標準（Qt 用 offscreen 煙霧測，照既有 pattern）

- 參照 repo 既有 `tests/test_output_center_ui_smoke.py` 的 offscreen 寫法（`QT_QPA_PLATFORM=offscreen` + `QApplication`）。
- 新增 `tests/test_change_order_wizard_smoke.py`：注入 **fixture-backed builder**，程式化驅動對話框：
  - 設流水號「**088**」+ 日期 → 斷言 `co.series` 正規化成「88」、存出的 id 是「**88_…**」（**不是**「088_…」）。← 修好 flag 的證明
  - 加一個既有焊口（fixture 有 `2`、`2a`）→ 斷言該列 `code`＝「**2b**」、規格從 fixture 帶入、`spec_source=looked_up`。
  - **連加兩個新焊口 → 斷言 `1001`、`1002`**（薄殼有正確透過 builder 合併，不重號）。
  - 移除清單中一個再看 → 重放後 `code` 仍一致。
  - 觸發「存草稿」→ 斷言 JSON 檔生出、`ChangeOrder.load_json` 讀回來內容對。
- 對話框能在 offscreen 下建構，不需真實螢幕。
- 全套 `pytest`：新測試綠 + **既有紅維持「剛好 15、同名」**（因為沒改既有檔，舊測試應全不動）。

---

## 交付格式

1. 先貼 `git diff --stat` ＋ UI 類別/結構大綱，等確認。
2. 一個 commit：`feat(wizard2): add source-driven weld entry slice on ChangeOrderBuilder (Task 5)`。
3. 回報：測試結果、確認既有 15 紅未變、有無觸禁區（應為無）、對 **Task 6**（照片 / PDF / 材料 + 真實資料夾複製）的銜接建議。
4. git / commit 由你（Codex）原生執行；**diff-first 給人看過再 commit**。然後 STOP。

---

*權威型別與服務以 `control/change_order.py`、`control/change_order_builder.py` 為準；UI 應為薄殼，邏輯不重寫。`records_root` 的資料夾慣例為暫定，Task 6 會正式定 attachments 結構。*
