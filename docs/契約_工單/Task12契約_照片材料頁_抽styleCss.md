# Task 12 契約：新精靈 ③照片 ④材料頁 ＋ 抽出 style.css（給 Codex）

> **前置**：讀 `control/co_wizard_web/index.html`（②焊口頁的 pattern）、`control/co_bridge.py`（橋 API）。設計沿用既有 class、tokens，**不要發明新樣式**。
> 前端工作，**引擎 / 橋不動**。diff-first、守禁區、STOP。

---

## 先做：鎖住設計基準線（重要）

目前 `index.html` 累積了一輪外觀調整（mac 化、側欄立體、脈動提醒、按鈕反應）但**還沒 commit**。**先單獨 commit 它**，別弄丟：

```
style(wizard-web): mac-style polish, 3D sidebar, hint pulse, button feedback
```

然後再開始下面的 Task 12。

---

## 做什麼（只動 `control/co_wizard_web/` 前端）

1. **③ 照片圖面頁**（取代現有「下一刀補」佔位）：
   - 「加修改前 / 加修改後」按鈕 → `await call('pick_file','image')` → 推進 `state.photos`（`{role,file}`）→ `rebuild()`；列出已選（角色 + 檔名）+ 移除鈕。
   - 「選圖面 PDF」→ `call('pick_file','pdf')` → `state.drawing_pdf` → 顯示檔名 + 可清除。
   - **不用改後端**：`build` / `export` 已吃 `state.photos` / `state.drawing_pdf`，照片會在出單時被複製。
2. **④ 材料頁**（取代佔位）：
   - 表單（零件 / 尺寸 / SCH / 材質 / 數量 / 單位 / 備註）→ 推 `state.materials` → `rebuild()`；列出 + 移除。後端 `build` 已支援（未知欄會被濾）。
3. **抽出 `style.css`**：把 index.html 整段 `<style>…</style>` 移到 `control/co_wizard_web/style.css`，index.html 改用 `<link rel="stylesheet" href="style.css">`。**務必確認 pywebview 載入後樣式仍正常套上**（相對路徑要對；打包 `--add-data` 要含這個檔）。
4. **（可選）接續 hint guide**：照片/材料現在能輸入了，`updateHints()` 可往下接（缺 before/after/pdf → 提示 ③ 照片頁；補齊 → 提示「正式建立」）。不勉強。

---

## 設計一致（別走鐘）

- **沿用既有 class**（`.sheet`、`button` / `button.primary`、`table`、`.empty`、`.pill`、`--brand` tokens…）→ 外觀自動一致，**不要新增風格**。
- 空狀態可用同款克制線稿（品牌藍）。

---

## 硬禁區

- 不改 `co_bridge` / `change_order*` / `weld_*` / `change_order_builder` / `change_order_store` / `co_wizard_app.py`。
- 不碰 `gui.py` / 舊 `wizard.py` / renderers。
- 不碰那 15 個既有紅。

---

## 驗收（GUI — **不要截圖 / 點座標自驗**）

- `pytest tests/test_co_bridge.py -q` 仍綠（橋沒動）。
- `python control\co_wizard_app.py` 啟動無 traceback；**抽出 css 後樣式仍正常**（console 無 404 / 載入錯誤）。
- 回報「啟動成功 ＋ 改了哪些檔」；**加照片 / 材料、出單的互動與外觀由使用者親看**。

---

## 交付

1. 先貼 `git diff --stat`，等確認。
2. **兩個 commit**：① 上面的 baseline polish；② `feat(wizard-web): photos & materials pages + extract style.css`。
3. `build/` `dist/` 不進 git。diff-first 給人看過再 commit，然後 STOP。
