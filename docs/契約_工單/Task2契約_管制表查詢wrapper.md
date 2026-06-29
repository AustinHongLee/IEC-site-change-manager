# Task 2 契約：管制表查詢 wrapper（給 Codex）

> **前置**：先讀 `執行指導書_新修改單系統_v1.md` 的 §C 領域知識、§D 原則、§E 紀律。本檔只給 Task 2 專屬內容，紀律照指導書。
> **鐵律**：一任務一 commit、`git diff --stat` 先給人看再 commit、守硬禁區。做完 STOP 回報。

---

## 目標

做一層**唯讀**的乾淨介面 `control/weld_lookup.py`，包既有 `weld_control` / `settings_manager`，給新系統用兩件事：

1. **查規格**：給 (流水號, 原始焊口 base) → 回 `change_order.Spec`。
2. **列既有 / 驗衝突**：列出某流水號已存在的焊口編號、判某編號是否已存在。

**不做**編號推導（a/b/c、1000+ 是 Task 3）、**不寫表**（write-back 是後話）。

---

## 你要先知道的既有程式事實（已替你讀過，照這個包）

- `settings_manager.get_weld_control_config()` 回 `{file_path, sheet_name, col_serial(預設 "流水號"), col_weld_no(預設 "焊口編號"), auto_sync, check_duplicate, dynamic_columns}`。**注意它沒回 `serial_format`**；要的話用 `get_settings().get("weld_control","serial_format","raw")`，預設 `raw`。
- `weld_control.init_weld_manager_from_settings()` → 設定好的單例 manager（或 `None`）。`manager.load()` 智慧快取載入、`manager.is_configured()`。
- manager 查詢（內部都會先 `load()`）：
  - `get_weld_info(serial, weld_no) -> dict | None`：單筆。
  - `get_all_welds_by_serial(serial) -> list[dict]`：O(1) 索引，回該流水號**所有**列。
  - `check_exists(serial, weld_no) -> bool`。
- **回傳 dict 的鍵 = Excel 實際表頭原字串**（`流水號 / 圖號 / 銲口編號 / 尺寸 / 厚度 / 材質 / 銲接型式 / 屬性.1 / …`），值已 JSON-safe（datetime→isoformat）。
- serial 內部以 `str(serial).strip()` 比對；表內存 raw int → `"1"…"317"`（**無補零**）。查詢前要把流水號正規化成 raw（去前導零）才對得上。
- 表頭「焊 / 銲」變體用 `utils.resolve_col(name, col_map_or_keys)` 容錯（manager 內部主鍵已用它；你對 `尺寸/厚度/材質/銲接型式/屬性.1` 也要用它）。
- **屬性.1 過濾**：`get_all_welds_by_serial` 會把「焊口 / 管牙 ＋ VALVE / 法蘭 / 控制閥 安裝計量」**全部**吐回。真實接點只取 `屬性.1 ∈ {焊口, 管牙製作安裝}`；安裝計量列不是焊口，要濾掉。

---

## 範圍（只新增，不改既有檔）

- 新增 `control/weld_lookup.py`
- 新增 `tests/test_weld_lookup.py`
- **不改** `weld_control.py` / `settings_manager.py` / 任何既有檔。

---

## 要做的事（建議簽名，可微調但回報要說明）

```python
class WeldLookup:
    def __init__(self, manager=None, *, serial_format="raw"):
        # manager 預設 init_weld_manager_from_settings()；測試可注入指向 fixture 的 manager

    def lookup_spec(self, series, base) -> "Spec | None":
        # 在「真實焊口列」中找 (正規化 series, base)
        # → 映 尺寸→size、厚度→sch、材質→material、銲接型式→weld_type（用 resolve_col 容錯欄名）
        # 找不到回 None。回 change_order.Spec（不設 spec_source）。

    def existing_weld_ids(self, series) -> list[str]:
        # 該流水號所有「真實焊口」的 銲口編號字串（給 Task 3 算編號 / 防衝突）

    def exists(self, series, weld_id) -> bool:
        # 該編號是否已存在（薄包 check_exists）
```

- **正規化 series**：raw（去前導零；空字串給 `"0"`）。`"0202"`、`"202"`、`202` 要視為同一個。
- **spec_source 不在這裡碰**：`lookup_spec` 回 `Spec` 時，**呼叫端**負責 `WeldEvent.spec = 回傳值; spec_source = LOOKED_UP`；回 `None` 時呼叫端手填 + `MANUAL`。
- **依賴方向單向**：`weld_lookup` 可 `from change_order import Spec`；`change_order` 永遠不反向依賴 `weld_lookup`。

---

## 硬禁區（絕對不碰）

- **唯讀**：不呼叫 `add_weld` / `add_new_welds`、不寫任何 xlsx。
- 不實作 a/b/c 或 1000+ 編號（那是 Task 3）。
- 不 `import PyQt6`、不碰 wizard / gui / renderers / 設定流程。
- 不改既有模組。
- **不碰那 15 個既有紅的 PDF / 輸出測試**（基準線已知 15 紅，與本任務無關，維持 15、不准順手修）。

---

## 驗收標準

- 用 **openpyxl 造一個 fixture xlsx** 注入 manager 來測（不依賴真實共用表路徑）：
  - fixture 表頭故意用「**銲**口編號」變體 + 含 `屬性.1` 欄；放幾列焊口 + 至少一列 `VALVE安裝`（屬性.1）。
  - `lookup_spec` 對既有焊口回正確 `Spec`（尺寸/厚度/材質/型式對映正確）；對不存在的 base 回 `None`。
  - **屬性.1 過濾**：VALVE / 法蘭列不被當焊口（不出現在 `existing_weld_ids`；`lookup_spec` 不把它當焊口回）。
  - `existing_weld_ids` 只含真實焊口。
  - `exists` 正確。
  - **序號正規化**：`"0202"` / `"202"` / `202` 查同一筆都命中。
  - **焊 / 銲 變體**：fixture 用「銲口編號」表頭仍能正確查到。
- headless import、無 Qt 依賴。
- 全套 `pytest`：新測試綠 + **既有紅維持「剛好 15、同名」**（多一個就是你弄壞了東西，要查）。

---

## 交付格式

1. 先貼 `git diff --stat` ＋ 新檔 API 大綱，等確認。
2. 一個 commit：`feat(lookup): add read-only WeldLookup over weld_control (Task 2)`。
3. 回報：測試結果（通過數）、確認既有 15 紅未變、有無觸禁區（應為無）、對 **Task 3** 的銜接建議（codec 吃 `origin / base / rework_index` ＋ `existing_weld_ids` → 產 `code`）。
4. git / commit 由你（Codex）原生執行；**diff-first 給人看過再 commit**。然後 STOP，等下一份契約。

---

*權威資料型別（`Spec` 等）以 `control/change_order.py` 為準；領域規則與紀律以 `執行指導書_新修改單系統` 為準。*
