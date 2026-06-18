# Opus 校準結果 — C5：舊 Excel COM 輸出邊界收斂（吹毛求疵級）

對應：Checkpoint C 剩餘高風險項 C5。
審查日期：2026-06-16
審查方式：直接讀 import 邊界與呼叫鏈；新管線 COM-free 已於 Checkpoint C 沙箱無 win32com 環境實跑確認。

---

## 0. 一句話結論

**C5 不是「要不要重寫輸出」的問題，是「COM 現在是不是啟動硬依賴」的問題——而它是。**
`excel_handler.py` 在模組頂層 `import win32com`，`gui.py` 又在模組頂層 `import excel_handler`。
**所以在沒有 pywin32 / Excel 的機器上，GUI 連啟動都會失敗**——這對「單一 exe、公司級部署」是直接致命傷。
好消息：新核心（canonical / template / dry-run / validate / xlsx renderer / 統計單）**已實測在無 win32com 環境跑得起來**。
所以 C5 的最小工作不是搬輸出，是**把 import 邊界切乾淨**，讓 COM 變成「有就用、沒有就灰掉」的可選後端。

---

## 1. 現況事證（讀碼確認）

- `control/excel_handler.py:18-19`：`import win32com.client` 在**模組頂層**。任何人 import 它就觸發 COM import。
- `control/gui.py:71`：`from excel_handler import (...)` 在**模組頂層**。→ **GUI 啟動鏈硬依賴 win32com**。
- `control/main.py:193`：`from excel_handler import ...` 在 **CLI 函式內**（lazy），相對安全，但仍是無條件載入。
- 全 `control/` 只有 `excel_handler.py` import win32com（已 grep 確認）。
- 新模組 `canonical_report / canonical_fields / template_mapping / template_dry_run / xlsx_template_renderer / site_statistics_exporter` 皆 COM-free（Checkpoint C 在無 win32com 沙箱實跑通過）。

**漏洞定位**：不是「核心污染」，而是「**GUI/CLI 進入點在 import 期就把 COM 拉進來**」。把這條切掉，COM 即可降級。

---

## 2. 回答你的八個問題

### Q1. 舊 COM 輸出應如何降級為 optional renderer？
三件事，缺一不可：

1. **Lazy import**：`import win32com` 從模組頂層移進 `ExcelManager` 真正要用的方法裡；`excel_handler` 不在任何啟動路徑被頂層 import。
2. **能力探測**：新增 `capabilities.py`，`detect_excel_com()` 試探一次（try import + DispatchEx 測試），結果快取。UI/registry 用它決定 COM 輸出可不可選。
3. **收進 renderer registry**：COM 變成一個註冊的 renderer（`kind="xlsx_com"`），介面與 `xlsx_template_renderer` 一致（`available`、`render(plan)`）。**它吃 CanonicalReport，不另開資料路**——只是換一個畫圖後端，不是換一套資料。

預設輸出走 openpyxl / PDF；COM 只在使用者明確選「高保真/舊模板」或模板宣告 `kind: xlsx_com` 時才載入。

### Q2. 哪些核心模組絕對不應 import win32com / Excel COM？
**任何在 GUI/CLI 啟動期會被 import 的模組，都不得（直接或間接）拉進 win32com。** 明確清單：

- 資料核心：`canonical_report`、`canonical_fields`、`record_manager`、`parsers`、`utils`、`config`、`settings_manager`、`image_processor`
- 模板/輸出契約：`template_mapping`、`template_dry_run`、`validate_template`（工具）、`xlsx_template_renderer`、`site_statistics_exporter`
- 守門/稽核/健康檢查：`project_guard`、`integrity_audit`、`operation_journal`、`_audit_data`
- 材料/請款線：`material_*`、`billing_*`
- **GUI 殼啟動路徑與 CLI 進入點的 import 期**（目前 `gui.py` 違規）

規則寫成自動測試（見 Q6 #1）：把 win32com 設為不可用後，這些模組都要 import 成功，且不得把 win32com 帶進 `sys.modules`。

### Q3. 過渡順序（不要一次改爆）
嚴格由「最便宜、最解耦」往「最動輸出」排：

1. **Step 1（純隔離，零輸出行為改變）**：excel_handler 內 lazy import win32com；gui.py 改成在「使用者按產出 COM 輸出」時才 import excel_handler。加 `capabilities.excel_com` 探測。
   → **光這步就讓「沒有 Excel 也能開 App」成立**，風險最低、收益最高。
2. **Step 2**：建 renderer registry + kind 分派；UI 依能力探測灰掉 COM 選項。舊 COM 修改單輸出仍是預設，但已可選、已被守住。
3. **Step 3**：讓 COM renderer 改吃 CanonicalReport（資料路統一），但**輸出外觀維持不變**，用 golden-file 比對舊 PDF。
4. **Step 4**：做出 openpyxl/LibreOffice 版的修改單 PDF，與舊版比對一致後，**才**把預設切到非 COM；COM 降為「舊模板/高保真」後備。

不可顛倒：**先隔離（解除部署風險），再統一資料，最後才搬輸出。**

### Q4. 哪些先保留舊路線、哪些先導到 CanonicalReport？
- **先保留舊 COM 路線**：現有「每張修改單的固定公司 Excel 模板 + macro 貼圖 + 匯出 PDF」這條已被現場依賴、視覺已調好的輸出。**會動的先別碰。**
- **先導到 CanonicalReport**：新統計單（已完成）、以及**所有新公司格式需求**——一律走新 template renderer，**絕不為新格式寫新 COM 程式碼**。
- 一句話準則：**新格式一律走新路；舊的會動的先別動。**

### Q5. C5 的最小可驗收成果（MVA）
**部署關鍵那一條**：在**沒有 pywin32 / Excel** 的機器上——

- App 能啟動；
- `--health-check`、canonical 收斂、dry-run、validate_template、xlsx_template render、統計單匯出**全部成功**；
- 只有「COM 輸出」這個選項被停用，並給清楚訊息（不是崩潰、不是 traceback）。
- 附一個**自動 import-guard 測試**：任何核心模組在 import 期拉進 win32com 就失敗。

**不在 MVA 內**：把舊 PDF 搬上 canonical、移除 COM、做 LibreOffice 轉檔。那些是 P2。

### Q6. 需要的自動 + 人工測試
**自動**：
1. **Import-guard**：把 `win32com` 設為不可用（`sys.modules["win32com"]=None` 或 stub raise），斷言 Q2 清單模組與 GUI 啟動模組都能 import，且 import 後 `sys.modules` 不含 win32com。
2. **能力探測**：`detect_excel_com()` 在無 COM 時回 False 且不丟例外；有 COM 時 True。
3. **Registry**：COM renderer 在探測 False 時 `available=False`；被選到時回友善錯誤，不崩。
4. **無 COM 煙霧**：health-check / dry-run / validate / xlsx render / 統計單，在無 win32com 環境全綠（CI 用非 Windows runner 即可天然驗證）。

**人工（Windows）**：
1. 有 Excel 機器：COM 輸出產出的 PDF 與改版前**視覺一致**（golden 對比）。
2. 無 Excel 機器（或暫時改名 pywin32）：App 啟動、統計單與 xlsx 模板輸出可用、COM 選項灰掉並有提示。
3. 產出中途強制關閉 Excel：**不留殭屍 EXCEL.EXE**，App 能回復。
4. PyInstaller 單一 exe 丟到沒裝 Office 的乾淨機器：能啟動並完成非 COM 輸出。

### Q7. 未來要支援「PDF 拉框 / Excel 貼照片 / 各公司格式」，C5 現在不能做錯的設計
1. **不要讓 COM 成為唯一的貼照片路徑。** openpyxl 內嵌圖片（xlsx_template_renderer 已有）必須是「貼照片到 Excel」的正規路；COM macro 貼圖只能是 legacy。否則未來「貼照片」又被綁回 COM，自己跳回陷阱。
2. **renderer 選擇不可用 mode 硬寫 if 樹。** 由模板宣告 `kind`（`xlsx_template` / `xlsx_com` / `pdf_overlay`），registry 分派。新增公司格式 = 選/寫一份模板 + 指定 kind，**永不改分派邏輯**。
3. **COM 專屬假設（`get_template_for_mode` 的 cell ranges、macro 名稱）不可滲進 canonical 模型或通用模板 schema。** 通用 schema 必須 renderer-agnostic；COM 細節只活在 COM renderer 與它自己的模板變體裡。
4. **能力探測集中化**：PDF（要字型）、LibreOffice（要 soffice）、COM（要 Excel）統一在 `capabilities` 回報可用性，UI 用同一套邏輯灰掉。
5. **COM 不可成為繞過驗證的後門。** 任何 renderer（含 COM）都要先過 validate_template + dry-run，不准有「COM 直出」跳過閘門的路。

### Q8. P0 / P1 / P2 修正清單

**P0（影響公司級穩定性或架構方向，必做）**
1. `excel_handler.py`：win32com 由頂層改為方法內 lazy import。
2. `gui.py`：移除頂層 `import excel_handler`，改為使用者觸發 COM 輸出時才 lazy import。（1+2 合起來＝「無 Excel 也能開 App」成立）
3. 新增 `capabilities` 模組（`excel_com` 探測，快取）＋ **import-guard 自動測試**（核心模組 import 期 COM-free）。
4. Renderer registry + `kind` 分派；COM 收為其中一個 backend，且**吃 CanonicalReport，不另開資料路**。

**P1（穩定可用、過渡安全）**
5. UI 依能力探測灰掉 COM 輸出並給人話提示；現場使用者不需理解 template/renderer/COM。
6. Excel→PDF 預設改 LibreOffice headless；COM 僅後備。
7. 切換預設前，舊 COM PDF vs 新路 golden-file 比對。
8. COM 程序衛生：crash / 中止不留殭屍程序，且只在 COM renderer 內被觸發。

**P2（長期收斂）**
9. 把每張修改單 PDF 搬上 canonical + 非 COM renderer，比對一致後切預設；COM 標為 legacy。
10. 最終移除 COM，或拆成獨立 optional 外掛（隨機器有無 Office 安裝）。

---

## 3. 與你給的限制對齊

- **不重寫整個輸出系統**：P0 只做 import 隔離 + 能力探測 + registry 介面，不動既有輸出外觀；搬輸出排到 P2。
- **不讓 COM 成為核心/健康檢查/dry-run/validation 的必要依賴**：P0 #1-3 直接保證，並用 import-guard 測試鎖住。
- **現場使用者不需懂 template/renderer/COM**：P1 #5；他們只看到「選模板→預檢→產出→看問題」，COM 不可用就是該選項灰掉。
- **務實、可分階段**：四步過渡，先隔離後搬遷，每步可獨立驗收。

---

## 4. 一句話

C5 真正的雷不在「兩條輸出路並存」，在「**GUI 啟動就硬綁 COM**」。
先把 `gui.py → excel_handler → win32com` 這條頂層 import 鏈改成 lazy + 能力探測（P0 #1-3），
「沒有 Excel 也能開 App、能跑核心」就成立——這是公司級部署的地基，其餘都可以慢慢搬。
