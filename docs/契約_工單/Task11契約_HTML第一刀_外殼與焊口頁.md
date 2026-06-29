# Task 11 契約：新精靈 HTML 第一刀 — 品牌 app-shell ＋ 焊口頁（給 Codex）

> **前置**：讀 `新精靈完整規劃_v0.1.md`（尤其 **§0.5 設計定案**）、`control/co_bridge.py`（橋，JS 用 `pywebview.api.*`）、`control/co_wizard_web/index.html`（現有最小前端，直接長在它上面升級）。
> 把 spike 的最小前端，升級成**正式的智源品牌版**第一刀：外殼 ＋ 焊口頁。**引擎 / 橋不動。** diff-first、一 commit、STOP。

---

## 做什麼（只動 `control/co_wizard_web/` 的前端）

1. **app-shell 外殼**（照 §0.5）：
   - 左側**品牌藍導航列**：logo（用 `ref/` 的圖檔，沒有才退佔位圓徽）＋「智源工程・修改單系統」＋ 四步驟 `① 基本 / ② 焊口 / ③ 照片圖面 / ④ 材料` ＋ 底部「圖號 X · 已連線」。
   - 右側**一次只顯示一段**；底部固定**狀態列 ＋ 存草稿 / 正式建立**。
2. **① 基本資料頁**：流水號 ＋「載入焊口」按鈕 ＋ 日期 ＋ 原因。
3. **② 焊口頁（完整，源頭驅動）**：
   - 載入該流水號的**現有焊口清單**（可挑）→ 選操作 → 加入（走 `api.existing_welds`）。
   - 新焊口區（操作 + 規格）。
   - 「本單焊口」清單：自動碼（`5b` / `1001`）＋ 規格 ＋ 來源（走 `api.build`）。
4. **狀態列**：每次變更即時 `api.build` → 顯示「完整 / 待補 ＋ 缺什麼」（中文）；存草稿 / 正式建立呼叫 `api.export`。
5. **③ 照片、④ 材料**：這一刀先放**佔位**（導航切得過去、顯示「下一刀補」），不必做完。
6. **視覺照 §0.5**：淺色企業風、品牌藍 `#1860ab`、**留白與層次分區（別把每塊都框起來）**。意象**選用、克制**（線稿、品牌藍，放空狀態 / 步驟小圖示；不要滿版背景 / 漸層）。生成圖放 `control/co_wizard_web/img/`。

---

## 硬禁區

- 不改引擎 / 橋（`co_bridge` / `change_order*` / `weld_*` / `change_order_builder` / `change_order_store`）。
- 不改 `gui.py` / 舊 `wizard.py` / renderers。
- 不碰那 15 個既有紅。

---

## 驗收（GUI — 照新規矩：**不要截圖 / 點座標自驗**）

- `pytest tests/test_co_bridge.py -q` 仍綠（橋沒被動到）。
- `python control\co_wizard_app.py` **啟動不報錯**、console 乾淨（沒有 JS / Python traceback）。
- 回報「app 啟動成功 ＋ 你動了哪些檔」即可；**互動 / 視覺由使用者親自開來看**（你不用截圖驗，省 token）。

---

## 交付格式

1. 先貼 `git diff --stat` ＋ 改了哪些前端檔 / 新增哪些圖，等確認。
2. 一個 commit：`feat(wizard-web): branded app-shell + welds page on bridge (Task 11)`。
3. `build/` `dist/` 不進 git。diff-first 給人看過再 commit，然後 STOP。

---

*設計權威以 `新精靈完整規劃_v0.1.md` §0.5 為準；橋的 API（`existing_welds` / `build` / `export` / `pick_file` / `info`）以 `control/co_bridge.py` 為準，前端不重寫邏輯。*
