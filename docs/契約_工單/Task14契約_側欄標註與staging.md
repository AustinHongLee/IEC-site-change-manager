# Task 14 契約：側欄收尾 — 標註 + staging（給 Codex）

> 前置：`co_wizard_web/index.html`、`co_bridge.py`，設計沿用既有 class/tokens。diff-first、STOP。
> 做完這刀，側欄三塊（歷史 ✅ / 標註 / staging）就到齊。**前端為主，橋只新增唯讀/工具方法。**

---

## A. staging 快速匯入
- 橋加 `list_staging()` → 列出 staging 資料夾的圖檔 `[{name, path}]`（沿用舊的 `<project>/staging/`，或 attachments_root 旁，你定）。唯讀、信封、壞檔略過。
- 前端側欄列出 staging 縮圖/檔名 → 點一下加成 before/after（角色用按鈕選）→ 進 `state.photos` → `rebuild()`。

## B. 標註（canvas）
- 在「已選照片」上開標註層（HTML `<canvas>` 疊圖）：畫筆 / 箭頭 / 文字 / 清除 / 復原。
- 存：canvas 合成 → 送 dataURL 給橋 `save_annotated(data_url, base_name)` → 寫成 PNG（attachments_root 旁的暫存）→ 回 path → 取代該照片的 `file`。
- **PDF 標註較重（需 pdf.js）。這刀先做「照片」標註即可；PDF 標註若工太大，先略過並回報，當下一刀。**

---

## 一致 / 硬禁區
- 沿用既有設計 class，別新增風格。
- 橋只能**新增** `list_staging` / `save_annotated`；**不改**既有橋方法 / `change_order*` / `weld_*` / `builder` / `store` / `co_wizard_app.py` / `gui.py` / 舊 wizard / 那 15 個既有紅。

## 驗收（輕量，不要截圖自驗）
- `pytest tests/test_co_bridge.py -q` 綠（新方法各加一個簡單測：`list_staging` 列檔、`save_annotated` 寫出檔回 path）。
- `python control\co_wizard_app.py` 啟動無 traceback。
- 互動 / 外觀由使用者親看。

## 交付
- diff-first → 一個 commit：`feat(wizard-web): annotation + staging side panels (Task 14)`。`build/`/`dist/` 不進 git。STOP。
