# Task 10 契約：pywebview 落地 spike（給 Codex）

> **目標**：在這台真實 Windows 上**證明**「pywebview 桌面 UI + Python 引擎」跑得起來、也包得出 exe。
> 過 → 之後放心用 HTML 把新精靈做完；卡 → 當場知道要補什麼（WebView2 runtime / 或改 Tauri、Electron）。
> 這是**去風險**，不是做功能。檔案都已備好（`control/co_bridge.py`、`control/co_wizard_app.py`、`control/co_wizard_web/`），你只要跑 + 回報。

---

## 你（Codex）要做的（照順序，每步記結果）

1. **裝 pywebview**：`pip install pywebview`。記版本。
2. **橋自我驗**（真環境再跑一次，沙箱已綠）：`pytest tests/test_co_bridge.py -q`。應全綠。
3. **跑起來**：`python control\co_wizard_app.py`
   - 視窗開得起來嗎？標題列右上應顯示「已連線 · API 1.0」。
   - 若你能互動：填流水號（用一個你管制表裡真的有的圖號）→ 按「載入這張圖的焊口」→ 應列出焊口；挑一筆 + 加入 → 本單焊口應出現自動算的碼（如 `5b`）。
   - 若你開不了互動視窗：至少確認它**啟動不 crash**、把 console 輸出貼回來。
4. **打包**：照 `control/co_wizard_web/README.md` 的 `pyinstaller` 指令打包。exe 出得來嗎？
5. **跑 exe**：雙擊/執行產出的 exe。開得起來嗎？還是報缺 WebView2？

---

## 回報（這就是 spike 的產出）

逐步回：✅過 / ❌卡（附**確切錯誤訊息**）。重點問：
- pywebview 裝得起來嗎？
- `test_co_bridge` 在真環境綠嗎？
- app 啟動成功嗎？（或卡在哪）
- pyinstaller 包得出 exe 嗎？
- exe 在這台機器開得起來嗎？WebView2 在嗎？

---

## 硬禁區

- **不改引擎**（`change_order` / `weld_lookup` / `weld_codec` / `change_order_builder` / `change_order_store`）、不改 `gui.py` / 舊 `wizard.py`。
- 不碰那 15 個既有紅。
- spike 階段**先不要 commit**（除非要存打包設定）；這是驗證、不是交付功能。打包產生的 `build/` `dist/` 別進 git。

---

*跑完把結果貼回來，Opus 看完決定：全押 HTML/pywebview，還是改用別的殼。引擎與設計（智源 app-shell）兩條路都留著。*
