# Task 8 契約：把新精靈接進 gui.py 選單（**碰既有檔，嚴格模式**，給 Codex）

> **前置**：讀 `執行指導書_新修改單系統_v1.md` §C/§D/§E，以及 `change_order_wizard.py` 的 `ChangeOrderWizard.__init__` 簽名。
> **這是第一次碰使用者每天在用的 `gui.py`。改動鎖到最小，每一行都要能說明。** `git diff` 先給人看完整、一任務一 commit、守禁區、做完 STOP。

---

## 目標

在主視窗加一個入口，啟動新精靈（`ChangeOrderWizard`）。**舊「✨ 建立精靈」按鈕與其 `_launch_wizard` 一個字不動、照常能用。** 新舊並存。

---

## 既有 pattern（已替你讀好，照抄結構）

`gui.py` 現在掛舊精靈的三處：

- **匯入/旗標（48-52）**：
  ```python
  try:
      from wizard import launch_wizard
      WIZARD_AVAILABLE = True
  except ImportError:
      WIZARD_AVAILABLE = False
  ```
- **按鈕（347-351）**：`btn_wizard = QPushButton("✨ 建立精靈")` … `.clicked.connect(self._launch_wizard)` … `action_row.addWidget(btn_wizard)`
- **啟動方法（966-973）**：`_launch_wizard`：`if not WIZARD_AVAILABLE: warn; return` → `FolderWizard(self).show()` + `self.log(...)`

---

## 要做的事（只加，不改）

1. **平行的匯入/旗標區**（緊接舊的那段之後）：
   ```python
   try:
       from change_order_wizard import ChangeOrderWizard  # noqa: F401
       CHANGE_ORDER_WIZARD_AVAILABLE = True
   except ImportError:
       CHANGE_ORDER_WIZARD_AVAILABLE = False
   ```
2. **平行按鈕**（緊接 `btn_wizard` 那段後、同一個 `action_row`）：
   ```python
   btn_co_wizard = QPushButton("🆕 新修改單精靈 (Beta)")
   btn_co_wizard.setToolTip("啟動新版源頭驅動修改單精靈")
   btn_co_wizard.clicked.connect(self._launch_change_order_wizard)
   action_row.addWidget(btn_co_wizard)
   ```
3. **平行啟動方法**：
   ```python
   def _launch_change_order_wizard(self):
       if not CHANGE_ORDER_WIZARD_AVAILABLE:
           QMessageBox.warning(self, "功能不可用", "新修改單精靈模組未載入")
           return
       wiz = ChangeOrderWizard(attachments_root=ATTACHMENTS_ROOT)
       wiz.exec()
       self.log("🆕 已啟動新修改單精靈")
   ```

---

## ⚠ 三個一定要對的細節（不對就壞）

1. **`ChangeOrderWizard.__init__(self, builder=None, *, attachments_root=None)` 不收 parent。**
   **不可**寫成 `ChangeOrderWizard(self)`——那會把主視窗當成 `builder`，必爆。要用關鍵字 `attachments_root=...`，`builder` 留預設（它會自己建真實的 `ChangeOrderBuilder()`）。
2. **生命週期**：新精靈無 parent。**用 `.exec()`（模態）**最安全。若用 `.show()`，`wiz` 是區域變數會被 GC、視窗瞬間消失——所以**用 `.exec()`**。
3. **`attachments_root`**：傳明確路徑（用 gui 既有的 `ATTACHMENTS_ROOT`，已 import）；**別**讓它落到預設的 `cwd`（不可預期）。

---

## 硬禁區（嚴格）

- `gui.py` **只允許新增上面三塊**；**任何既有行（含舊 `btn_wizard` / `_launch_wizard`）不得修改、刪除、移位**。
- 不碰 `wizard.py` / `change_order_wizard.py` / renderers / 其他既有檔。
- 不碰那 15 個既有紅。

---

## 驗收標準

- `git diff --stat` 應**只有 `gui.py`**（＋視情況一個小測試檔）；`git diff control/gui.py` 內容應**只看到那三塊新增，沒有任何既有行被改動/位移**。
- `gui.py` 仍能**乾淨 import**（新 import 有 try/except 包著，缺模組也不崩）。
- （建議、且要非脆弱）加輕量測試：`import` gui 模組 → 斷言 `CHANGE_ORDER_WIZARD_AVAILABLE is True`、`hasattr(<MainWindow 類>, "_launch_change_order_wizard")`。**不要**建構整個 MainWindow（太重/易碎）。
- 全套 `pytest`：**既有紅維持剛好 15、同名**，其餘全綠（尤其任何 gui smoke 測試不得壞）。

---

## 交付格式

1. 先貼 `git diff --stat` ＋ **完整 `git diff control/gui.py`**（碰既有檔，我要逐行看），等確認。
2. 一個 commit：`feat(gui): add launcher for new ChangeOrder wizard alongside old one (Task 8)`。
3. 回報：測試結果、確認既有 15 紅未變、**確認舊 `_launch_wizard` / `btn_wizard` 未被動**、`git diff --check` 乾淨。
4. git / commit 由你（Codex）原生執行；**這張我要看完整 gui.py diff 才放行**（碰生財工具）。然後 STOP。

---

*`ATTACHMENTS_ROOT` 是 gui.py 既有 import（來自 `config`）。新精靈型別/簽名以 `control/change_order_wizard.py` 為準。完成後新精靈正式可從主畫面開啟，舊精靈並存不受影響。*
