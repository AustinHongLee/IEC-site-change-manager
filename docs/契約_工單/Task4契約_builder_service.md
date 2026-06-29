# Task 4 契約：ChangeOrder builder service（headless，給 Codex）

> **前置**：先讀 `執行指導書_新修改單系統_v1.md` §C/§D/§E，以及三個已完成模組的公開 API：`control/change_order.py`、`control/weld_lookup.py`、`control/weld_codec.py`。
> **鐵律**：一任務一 commit、`git diff --stat` 先給人看再 commit、守硬禁區。做完 STOP 回報。

---

## 目標

做 `control/change_order_builder.py`：把「建立一張修改單」的**工作流邏輯**做成 headless 服務，串起三大基礎件。**不碰 Qt、不複製檔案、不寫磁碟**——只負責「組出一個正確、驗證過的 `ChangeOrder` 物件」。Qt UI（Task 5+）當薄殼接在上面。

## 定位（很重要）

這是把舊精靈的「腦」抽出來。所有「選流水號 → 撈原始焊口規格 → 加焊口事件 → 產碼 → 塞照片/PDF/原因/材料 → 算完整度」的**決策邏輯**都在這裡，用測試守住；Qt 只負責畫面 + 把使用者輸入餵進來。

---

## 依賴（注入式，保持可測）

- 建構子注入 `lookup`（預設 `WeldLookup()`）、`scheme`（預設 `WeldScheme()`）、`clock`（預設 `datetime.now`，給 audit / id 時間）。**測試注入指向 fixture 的 lookup ＋ 固定 clock**。
- import 方向單向：builder → `change_order` / `weld_lookup` / `weld_codec`。**不 import Qt**；import 本模組必須 headless。

---

## 要做的事（建議簽名，可微調但回報要說明）

```python
class ChangeOrderBuilder:
    def __init__(self, lookup=None, scheme=None, clock=None): ...

    def start(self, series, date, *, scenario=Scenario.NORMAL, dwg_no=None) -> ChangeOrder:
        # 建 draft（status=草稿）；dwg_no 沒給就試從 lookup 帶（該流水號的圖號，查無留空不崩）
        # audit.record("created")

    def add_existing_weld(self, co, base, op, *, joint_type=JointType.WELD) -> WeldEvent:
        # spec = lookup.lookup_spec(co.series, base) → 設 spec + spec_source=LOOKED_UP（查無：spec 留空、MANUAL）
        # code/rework_index = weld_codec.assign_event(EXISTING event, _existing_ids(co))
        # append 到 co.welds，回該 event

    def add_new_weld(self, co, op, spec, *, joint_type=JointType.WELD) -> WeldEvent:
        # code = weld_codec.assign_event(NEW event, _existing_ids(co), exists=<lookup.exists 綁 co.series>)
        # spec_source=MANUAL；append

    def add_photo(self, co, role, file, *, weld_ref=None) -> Photo: ...
    def set_drawing_pdf(self, co, file) -> None: ...
    def set_reason(self, co, text) -> None: ...
    def add_material(self, co, **fields) -> Material: ...
    def set_authorization(self, co, **fields) -> None: ...

    def validate(self, co, *, required=None) -> list[dict]:
        # 回缺漏清單，每筆 {"code":..., "field":..., "message":...}，不 raise
        # 硬底（一律必填）：至少 1 張 role=before + 1 張 role=after + drawing_pdf.file
        # required 可加更多欄位鍵（材料 / 簽認…），預設只有硬底

    def compute_status(self, co, *, required=None) -> Status:
        # validate 空 → Status.COMPLETE；否則 Status.PARTIAL（待補）

    def finalize_id(self, co, existing_ids) -> ChangeOrder:
        # co.id = generate_id(co.series, co.date, existing_ids)（用 change_order.generate_id）
```

---

## 關鍵正確性（務必處理，且要有測試）

- **`_existing_ids(co)` 必須把「`lookup.existing_weld_ids(co.series)`」＋「本張單已加進 `co.welds` 的 `code`」合併**。否則同一張單連加兩個新焊口會都拿到 `1001`。**這是必測點。**
- `spec_source`：既有焊口查到規格 → `LOOKED_UP`；查無或新焊口 → `MANUAL`。
- `start` 自動帶 `dwg_no` 可選失敗（查無就留空，不崩）。
- builder **不自己算** a/b/1000+（呼叫 `weld_codec`）、**不自己讀表**（呼叫 `weld_lookup`）。只做編排。

---

## 硬禁區（絕對不碰）

- 不 `import PyQt6`；不碰 wizard / gui / renderers。
- **不複製照片 / PDF、不建資料夾、不把 ChangeOrder 寫到磁碟**（序列化用既有 `ChangeOrder.save_json`，由上層呼叫；本任務只組物件 + 驗證）。
- 不改既有檔（`change_order` / `weld_lookup` / `weld_codec` 等）。
- 不碰那 15 個既有紅的 PDF / 輸出測試（維持剛好 15、同名）。

---

## 驗收標準（注入 fixture lookup，免真實表）

- 用 Task 2 那種 **fixture-backed `WeldLookup`** 注入測：
  - `add_existing_weld(co, base, 加長)`：spec 從 fixture 帶入、`spec_source=LOOKED_UP`、`code` 正確（如該流水號既有 `2`、`2a` → base `2` 得 `"2b"`）。
  - **同一張單連加兩個新焊口 → 依序拿到 `1001`、`1002`**（合併本單已用碼，不撞）。← 必測
  - `add_new_weld` → `spec_source=MANUAL`。
  - `validate`：缺 before / after / drawing_pdf 各報一筆 issue；補齊後回空。
  - `compute_status`：缺 → `待補`；齊 → `完整`。
  - `finalize_id`：同日同流水號遞增。
  - 固定 `clock` → audit `when` / id 可預期。
- headless、無 Qt 依賴。
- 全套 `pytest`：新測試綠 + **既有紅維持「剛好 15、同名」**。

---

## 交付格式

1. 先貼 `git diff --stat` ＋ 新檔 API 大綱，等確認。
2. 一個 commit：`feat(builder): add headless ChangeOrder builder service (Task 4)`。
3. 回報：測試結果、確認既有 15 紅未變、有無觸禁區（應為無）、對 **Task 5**（Qt 新精靈薄殼：畫面把輸入餵給 builder、最後 `save_json` + 複製檔案）的銜接建議。
4. git / commit 由你（Codex）原生執行；**diff-first 給人看過再 commit**。然後 STOP。

---

*權威型別與函式以 `control/change_order.py`（含 `generate_id`、`Status`、`Scenario`、`JointType`）為準；查詢語意以 `weld_lookup`、編號語意以 `weld_codec` 為準；領域規則與紀律以 `執行指導書_新修改單系統` 為準。*
