# Task 6 契約：ChangeOrder 匯出 / 持久層（headless，給 Codex）

> **前置**：讀 `執行指導書_新修改單系統_v1.md` §C/§D/§E，以及 `control/change_order.py` 的 API。
> **鐵律**：一任務一 commit、`git diff --stat` 先給人看再 commit、守硬禁區。做完 STOP 回報。

---

## 背景：這張只切「輸出落地」一塊

Task 5 的新精靈目前 `save_draft` 只寫一個 JSON。Task 6 把「真正落地」做成 **headless 服務**：建資料夾 + 把照片/PDF 複製進去 + 寫 record。**還是不碰 Qt、不碰 wizard**；Task 7 才讓精靈改用它。
（「照片/材料輸入 UI」「完整度 gating」「接 `gui.py` 選單」分別是 Task 7、Task 8，**別在這張做**。）

---

## 目標

做 `control/change_order_store.py`：把一個 ChangeOrder（其 `photos[].file` / `drawing_pdf.file` 指向**來源檔路徑**）落地成一個資料夾：

- 資料夾 ＝ `{attachments_root}/{co.id}/`
- 複製照片 → 規範檔名；複製圖面 PDF
- 寫 `change_order.json`，且**記錄裡的檔案引用改寫成資料夾內的相對檔名**（不再是來源絕對路徑）
- 來源檔不存在 → 記成 warning、跳過、**不崩**

---

## 要做的事（建議簽名，可微調但回報說明）

```python
@dataclass
class ExportResult:
    folder: Path
    record_path: Path
    copied: list[tuple[str, str]]   # (來源路徑, 目的相對名)
    missing: list[str]              # 找不到的來源檔

def export_change_order(co, attachments_root, *, overwrite=False) -> ExportResult:
    ...
```

- `co.id` 必須已設（呼叫端先 `finalize_id`）；沒有 → 明確 raise（給清楚訊息）。
- **不就地改傳入的 `co`**；在 copy 上改寫檔案引用後再序列化（`to_dict`/`from_dict` 或 `deepcopy`）。傳入的 co 其 `.file` 應維持原始來源路徑。
- **照片命名規範**：同 `role` 依序 `before_1.<ext>` / `before_2.<ext>` / `after_1.<ext>`…（保留原副檔名）；**單張也用 `before_1` / `after_1`**（一致、可預期）。
- **圖面 PDF** → `drawing.pdf`。
- `overwrite=False` 且資料夾已存在且內有 `change_order.json` → 明確 raise（不靜默覆蓋）；`overwrite=True` 才可重寫。
- 寫 JSON 用既有 `ChangeOrder.save_json`（已是原子寫入）。
- 複製用 `shutil.copy2`；先 `mkdir(parents=True, exist_ok=True)`。

---

## 硬禁區（絕對不碰）

- 不 `import PyQt6`；不碰 `wizard.py` / `gui.py` / `change_order_wizard.py` / 任何既有檔；**不接精靈**。
- 不算焊口編號、不查管制表（不是這張的事，別 import `weld_codec` / `weld_lookup`）。
- 不碰那 15 個既有紅的 PDF / 輸出測試。

---

## 驗收標準（temp dir + 假檔，免真實環境）

- 造 temp 來源檔（假 jpg/pdf：寫幾個 bytes 即可）＋ 一個 `co`（`id` 已設、`photos[].file` / `drawing_pdf.file` 指向那些來源；可用 `ChangeOrderBuilder` 或直接組）。
- `export_change_order` → 斷言：
  - 資料夾 `{root}/{id}/` 生出；照片/PDF 確實複製進去、檔名符規範（`before_1.jpg`、`after_1.jpg`、`drawing.pdf`…）。
  - `change_order.json` 生出；`ChangeOrder.load_json` 讀回後 `photos[].file` / `drawing_pdf.file` 是**相對檔名**（非原始絕對路徑）。
  - 缺一個來源檔 → 進 `result.missing`、不崩、其餘照樣複製。
  - 傳入的 `co` **沒被就地改**（它的 `.file` 還是原始來源路徑）。
  - `overwrite=False` 撞已存在 → raise；`overwrite=True` 可重寫。
- headless、無 Qt 依賴。
- 全套 `pytest`：新測試綠 + **既有紅維持「剛好 15、同名」**。

---

## 交付格式

1. 先貼 `git diff --stat` ＋ 新檔 API 大綱，等確認。
2. 一個 commit：`feat(store): add headless ChangeOrder export/persistence (Task 6)`。
3. 回報：測試結果、確認既有 15 紅未變、有無觸禁區（應為無）、對 **Task 7**（精靈加照片/PDF/材料輸入 + 完整度 gating + 改用此匯出層）的銜接建議。
4. git / commit 由你（Codex）原生執行；**diff-first 給人看過再 commit**。然後 STOP。

---

*權威型別與 `save_json` 以 `control/change_order.py` 為準；資料夾名 ＝ `co.id`（已含 series_date_seq，不另塞焊口清單）；領域規則與紀律以 `執行指導書_新修改單系統` 為準。*
