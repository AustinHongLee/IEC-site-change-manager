# 新精靈 — pywebview 橋 + spike

這是「丟掉 PyQt6、改用 HTML/JS 畫桌面 UI」的**橋**與**最小可跑 spike**。
引擎（`change_order` / `weld_lookup` / `weld_codec` / `change_order_builder` / `change_order_store`）一行沒動。

## 檔案
| 檔 | 角色 | 能不能無 GUI 測 |
|---|---|---|
| `control/co_bridge.py` | **橋**：transport-agnostic、JSON 進出、`{ok,data,error}` 信封。pywebview 拿它當 `js_api`，未來 FastAPI 也能直接包。 | ✅ 已用 `tests/test_co_bridge.py` 在沙箱實跑驗過 |
| `control/co_wizard_app.py` | pywebview 啟動器（開原生視窗、注入原生檔案對話框、WebView2 缺失防呆）。 | ✗ 需 pywebview，Windows 跑 |
| `control/co_wizard_web/index.html` | 最小前端：流水號 → 載入既有焊口可挑 → 加焊口（即時算碼）→ 照片/PDF/材料 → 狀態 → 出單。深色、中文。 | ✗ 需 webview |

## 跑（Windows）
```bat
pip install pywebview
python control\co_wizard_app.py
```
- 預設開 DevTools（WebView2 ＝ 完整 Chromium DevTools）；不要的話設環境變數 `CO_WIZARD_DEBUG=0`。
- 需要 **WebView2 Runtime**：Win11 / 更新過的 Win10 通常已內建；缺的話啟動器會印出提示，去 Microsoft 下載「Evergreen WebView2 Runtime」。

## 這就是 packaging spike：照這個驗，過了再全押
1. 上面能跑、視窗開得起來、能載入焊口 / 加焊口看到自動算碼（`5b` / `1001`）→ **橋通了**。
2. 打包：
   ```bat
   pip install pyinstaller
   pyinstaller --noconfirm --windowed --name 新修改單精靈 ^
     --add-data "control\co_wizard_web;co_wizard_web" ^
     control\co_wizard_app.py
   ```
   （`--add-data` 把 HTML 帶進去；路徑分隔在 Windows 是 `;`。若 import 缺東西，補 `--hidden-import`。）
3. 把產出的 exe 丟到**實際要部署的那種公司 Windows 機器**跑：裝得起來嗎？WebView2 在嗎？開得起來嗎？
   - **過** → 放心走 HTML/pywebview，接著把「新精靈完整規劃 v0.1」整套用 HTML 做。
   - **卡** → 只賠這點工，重新評估（Tauri / Electron / 或先把 Qt 精靈做完當過渡）。

## 橋的風險防護（為什麼說它「強」）
- **信封 + 例外護欄**：每個 API 方法 try/except 成 `{ok,data,error}`，前端永遠拿到可用結果、不會卡死或拿到半截例外。
- **無狀態 build**：前端送完整 payload，後端重放重算 → 沒有 stale state 問題。
- **檔案對話框用注入**：橋本身不 import pywebview → 純淨、可單元測；launcher 才注入原生對話框。
- **邊界防呆**：series 去前導零、op/role 容錯、材料未知欄位過濾——前端送髒資料也不炸。

## 未來換中央伺服器（為什麼這橋「以後不用重寫」）
`ChangeOrderBridge` 的方法是「JSON 進、JSON 出」，**不認傳輸層**。所以：
```python
# 今天（pywebview，本機、非 HTTP）
webview.create_window(..., js_api=ChangeOrderBridge())
# 以後（FastAPI，中央、HTTP）—— 方法簽名一行不用改
@app.post("/build")
def build(payload: dict): return bridge.build(payload)
```
前端從 `pywebview.api.build(payload)` 改成 `fetch("/build",{...})` 即可，UI 不用重畫。
