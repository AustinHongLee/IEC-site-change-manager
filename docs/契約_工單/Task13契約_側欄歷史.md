# Task 13 契約：新精靈側欄 —「歷史」（給 Codex）

> **前置**：讀 `control/co_wizard_web/index.html`、`control/co_bridge.py`、設計沿用既有 class/tokens。
> diff-first、守禁區、STOP。標註 / staging **不在這刀**（後續）。

---

## 目標

新精靈右側加一條**可收的側欄**，顯示「這張流水號（圖號）過去做過的修改單」（＝舊版「判讀流水號」那塊）。資料來源 ＝ 新系統已出單的紀錄。

---

## 做什麼

### A. 橋加一個唯讀方法（`co_bridge.py`，additive）
```python
@_enveloped
def history(self, series):
    # 掃 self.attachments_root 下 名稱以 "{正規化series}_" 開頭的資料夾
    # 讀各自的 change_order.json → 回 [{id, date, welds:[code...], reason, folder}]，日期新→舊
    # 讀不到 / 壞檔就略過，不崩
```
- 用既有 `_norm_series`；`"{s}_"` 前綴比對（底線可區隔 "1_" 與 "10_"）。
- 信封照舊。
- `tests/test_co_bridge.py` 加一個測：temp attachments_root 先寫兩筆 `{series}_date_NN/change_order.json`，`history(series)` 回得到、排序對、髒檔不崩。
- **（可選）** 再加 `open_path(path)` 用 `os.startfile` 開資料夾（Windows）；不做也行。

### B. 前端：右側「歷史」面板（`co_wizard_web/`）
- `.app` 加第三欄（約 300px）放歷史面板；**可一鍵收合**，窄視窗預設收起（@media）不要擠到主區。
- 流水號變更 / 載入時 → `call('history', series)` → 渲染卡片清單：**日期 · 焊口碼 · 原因**（＋若做了 open_path，加「開資料夾」鈕）。
- 空狀態：「這張圖號還沒有歷史修改單」。
- **沿用既有設計**（`.sheet` 風卡片、tokens、克制線稿），別新增風格。

---

## 硬禁區

- 橋只能**新增** `history`（＋可選 `open_path`）；**不改**既有橋方法 / `change_order*` / `weld_*` / `builder` / `store` / `co_wizard_app.py`。
- 不碰 `gui.py` / 舊 `wizard.py` / renderers / 那 15 個既有紅。
- 不做標註、不做 staging（後續刀）。

---

## 驗收（GUI — 不要截圖自驗）

- `pytest tests/test_co_bridge.py -q` 全綠（含新 history 測試）。
- `python control\co_wizard_app.py` 啟動無 traceback。
- 回報「啟動成功 ＋ 改了哪些檔 ＋ 新測試結果」；**面板外觀 / 收合 / 點擊由使用者親看**。

---

## 交付

1. 先貼 `git diff --stat` ＋ 新測試結果，等確認。
2. 一個 commit：`feat(wizard-web): history side panel + bridge.history (Task 13)`。
3. `build/` `dist/` 不進 git。diff-first 再 commit、STOP。
