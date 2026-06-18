# Opus 再校準請求：C5 COM 邊界與 Renderer Registry

請以產品架構師、Windows 桌面工具工程師、文件渲染工程師、公司級內部工具審查者角度，審查目前 C5 的最新狀態。

## 已完成

- `excel_handler.py` 不再於 import 期載入 `win32com`。
- `gui.py` 不再頂層 import `excel_handler`。
- 新增 `capabilities.py`，集中探測 Excel COM。
- 無 COM 時，GUI/核心模組仍可 import；舊 COM 產出入口會停用或人話提示。
- 新增 `renderer_registry.py` 與 `tools/list_renderers.py`。
- `render_xlsx_template.py` 已改走 registry 分派。
- `xlsx_template` 登錄為正式 CanonicalReport renderer。
- `xlsx_com` 登錄為 legacy optional backend，但標記 `CanonicalReport adapter pending`；透過 registry 選到時先回友善錯誤，不允許繞過 canonical/template 閘門直出。

## 請你審查

1. 目前 C5 是否已足以稱為「COM 從核心與啟動期降級」？
2. `xlsx_com` 目前登錄為 legacy optional、但 adapter pending，這個策略是否安全？
3. `list_renderers` 預設不啟動 Excel，只顯示 unprobed；`--probe-com` 才完整探測，這是否符合公司級 UX/效能？
4. GUI 舊產出目前仍是舊路線，只是在入口前做 COM guard；下一步應先接 registry，還是先做 CanonicalReport adapter？
5. `render_with_template()` 對 `xlsx_com` 回 `renderer_not_canonical_ready`，是否是正確防線，還是應該允許 legacy direct render？
6. 還有哪些 P0 風險會讓「單一 exe、無 Office 仍可啟動並使用非 COM 功能」不成立？
7. 下一個最小可驗收成果應該是：
   - A. GUI 全面讀 registry 顯示輸出選項
   - B. `xlsx_com` CanonicalReport adapter
   - C. `photo_sheet` renderer
   - D. LibreOffice capability / Excel→PDF 替代
   請排序並說明原因。

## 請輸出

- 結論：可繼續 / 需回補 / 架構方向需改
- P0 / P1 / P2 清單
- 必須新增的自動測試與人工測試
- 對「不要一次重寫舊 COM 報表」這條限制下的下一步建議
