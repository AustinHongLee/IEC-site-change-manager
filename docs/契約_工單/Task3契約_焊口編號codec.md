# Task 3 契約：焊口編號 codec（給 Codex）

> **前置**：先讀 `執行指導書_新修改單系統_v1.md` §C/§D/§E，以及 `Task2契約_管制表查詢wrapper.md`（了解 WeldLookup 提供 `existing_weld_ids` / `exists`）。本檔只給 Task 3 專屬內容。
> **鐵律**：一任務一 commit、`git diff --stat` 先給人看再 commit、守硬禁區。做完 STOP 回報。

---

## 目標

做 `control/weld_codec.py`：**純邏輯**，把「canonical 修改事件」⇄「案場焊口碼字串」雙向轉換，並依「既有焊口事實」算出新碼。

- **既有焊口重焊** → `code = base + 字母(a/b/c…)`，字母 = 第幾次重工。
- **全新焊口** → `code = 1000+ 的安全號`（高過該流水號所有現有焊口、不撞號）。
- **反向 parse** → 把案場碼拆回 `{base, 第幾次, 是否新焊口}`（讀舊資料 / 亂表用）。

---

## 領域規則（務必照這個，別自己發明）

- 原始焊口號 = 純數字（偶有 `w` 前綴）。`2` = 原始；`2a` = 第一次重焊；`2b` = 第二次。**字母 = 重工次數，不是操作類型**（裁切 / 加長 / 縮短**不影響**字母）。
- 全新焊口（原圖沒有）→ 取「高於該流水號所有現有焊口」的號碼、慣例 `1000+`，遞增避免撞號（第一個新焊口 = `1001`）。
- 一個操作可混合（加長 = 1 既有重焊 + 1 全新），但 **codec 只處理「單一焊口事件 → 單一碼」**；組合由上層決定。

---

## 資料來源（Task 2 的兩把鑰匙；但 codec 吃**純資料**，不直接吃 WeldLookup）

- `existing_ids: list[str]`（＝ `WeldLookup.existing_weld_ids(series)`，已濾真實焊口）→ 數某 base 重工幾次、找新焊口號的最大值。
- 可選 `exists: Callable[[str], bool]`（＝ `WeldLookup.exists(series, id)`，**含安裝列 PK**）→ 新焊口號最終防撞。
- **codec 保持純粹**：只 `import change_order` 型別 + stdlib；**不 import `weld_lookup` / `weld_control` / `openpyxl` / Qt**。上層 glue 才把 WeldLookup 接上。

---

## change_order.WeldEvent 相關欄位（已實作，照用）

`origin`（`Origin.EXISTING` / `Origin.NEW`）、`base`（原始號）、`op`（裁切/加長/縮短）、`rework_index`（第幾次）、`code`（**本任務要填**）。

---

## 範圍（只新增）

- 新增 `control/weld_codec.py`
- 新增 `tests/test_weld_codec.py`
- **不改**任何既有檔（含 `weld_lookup` / `change_order` / `weld_control`）。

---

## 要做的事（建議簽名，可微調但回報要說明）

```python
@dataclass
class WeldScheme:
    new_weld_base: int = 1000                       # 新焊口 floor；第一個 = base+1 = 1001
    rework_letters: str = "abcdefghijklmnopqrstuvwxyz"   # seq 1→'a'、2→'b'…

@dataclass
class ParsedCode:
    base: str | None
    rework_seq: int     # 0=原始, 1='a', 2='b'…
    is_new: bool
    raw: str            # 原字串
    parsed: bool        # 是否成功解析（亂碼=False 但不崩）

def parse(code: str, scheme: WeldScheme = WeldScheme()) -> ParsedCode:
    # "2"→base"2",seq0  /  "2a"→base"2",seq1  /  "2b"→seq2
    # 純數字且 ≥ new_weld_base → is_new=True
    # "w15" → 去前綴，base"15"
    # 無法解析 → parsed=False、raw 保留，不丟例外

def next_rework(base: str, existing_ids: list[str],
                scheme: WeldScheme = WeldScheme()) -> tuple[str, int]:
    # 在 existing_ids 中找同 base 的字母項，取最大 rework_seq → 下一個 = max+1
    # 回 (code=f"{base}{字母(下一個)}", rework_index=下一個)

def next_new(existing_ids: list[str], scheme: WeldScheme = WeldScheme(),
             exists: "Callable[[str], bool] | None" = None) -> str:
    # 候選 = max(scheme.new_weld_base, 現有所有純數字號的最大值) + 1
    #   （existing 全是設計號時 → 1001；已有 1001 → 1002）
    # 若 exists 提供，則自候選起遞增直到 exists(候選)==False
    # 回 str(候選)

def assign_event(event, existing_ids, *, exists=None,
                 scheme: WeldScheme = WeldScheme()):
    # EXISTING：填 rework_index + code（= next_rework(event.base, existing_ids)）
    # NEW：填 code（= next_new(existing_ids, exists=exists)）；rework_index 留空
    # 回填好的（copy，不就地改傳入物件）
```

---

## 硬禁區（絕對不碰）

- **純邏輯**：不 import `weld_lookup` / `weld_control` / `openpyxl` / `PyQt`；不碰檔案 / Excel / 網路。
- 不改既有檔；不寫表。
- 不碰那 15 個既有紅的 PDF / 輸出測試（基準線已知 15 紅，維持 15、不准順手修）。

---

## 驗收標準（純函式，免 fixture xlsx）

- **parse**：`"2"→(base"2",seq0,new=False)`、`"2a"→seq1`、`"2b"→seq2`、`"1001"→is_new=True`、`"w15"→base"15"`、亂碼 `"@@"→parsed=False 且不崩`。
- **next_rework**：`base"2", existing=["1","2","2a"] → ("2b",2)`；`base"5", existing=["5"] → ("5a",1)`；無前例 → `("Xa",1)`。
- **next_new**：`existing=["1","2","16"] → "1001"`；`existing=["1","1001"] → "1002"`；給 `exists` 說 `"1001"` 已佔 → 跳 `"1002"`。
- **一致性**：`parse(next_rework(base, ids)[0])` 的 base / seq 對得上。
- **assign_event**：EXISTING 事件得 `code`+`rework_index`；NEW 事件得 1000+ `code`。
- headless、無 Qt；全套 `pytest`：新測試綠 + **既有紅維持「剛好 15、同名」**。

---

## 交付格式

1. 先貼 `git diff --stat` ＋ 新檔 API 大綱，等確認。
2. 一個 commit：`feat(codec): add weld code codec for rework/new numbering (Task 3)`。
3. 回報：測試結果、確認既有 15 紅未變、有無觸禁區（應為無）、對 **Task 4**（新精靈 UI：選 base/op → codec 產碼 → 寫進 ChangeOrder）的銜接建議。
4. git / commit 由你（Codex）原生執行；**diff-first 給人看過再 commit**。然後 STOP。

---

*權威型別以 `control/change_order.py` 為準；資料來源語意以 `control/weld_lookup.py` 為準；領域規則與紀律以 `執行指導書_新修改單系統` 為準。*
