# 工務修改單企業級化指導書

> 產出：2026-07-09（Fable 5 審查）
> 審查基準：工作區 `main`（ahead of origin，另有 24 檔未 commit 修改 +2,932/-695、3 個未追蹤新檔）
> 審查方式：實際通讀 repo 原始碼與資料檔、於 Linux 沙箱實跑全套 pytest、以真實 `records/` 資料驗證疑點。**無法在使用者 Windows 實機驗證的項目均標註「需要實機驗證」。**
> 讀者：接手施工的 coding agent 與專案擁有者。每個問題都附「涉及檔案 / 建議作法 / 驗收標準」，可直接切任務。

---

## 0. 審查時的實測證據（後文引用）

先把這次審查實際跑出來的證據放在最前面，後文引用時標 `[E1]`～`[E7]`：

- **[E1] git 狀態**：`main` 分支、24 檔已修改未 commit（含 `co_main_bridge.py +617`、`co_main_web/index.html +932`、`owner_data_report.py +360`）、3 個未追蹤檔（`control/material_catalog_rules.py`、`records/material_catalog_rules.json`、`records/sample_generation_summary.json`）。另有 CRLF 警告（`records.json`、`settings.json` 在工作區為 CRLF）。
- **[E2] 測試（Linux 沙箱、Python 3.11、無 PyQt6、無 .git 副本）**：`447 passed, 14 failed, 3 skipped`，另 2 檔收集失敗。14 個 fail 全屬環境因素（9 個 `test_check_release_package_tool` + 4 個 `test_build_release_tool` 需要 git 環境；`test_capabilities`/`test_import_guard` 需要 PyQt6）。**真正壞掉的是 `tests/test_material_catalog_generator.py`：`from generate_material_catalog import build_catalog` ImportError**——未 commit 的工具重寫把 `build_catalog` 刪了，測試沒同步。使用者機器上另有「15 紅基準」（PDF overlay 相關，見記憶／docs），本次沙箱裝了 PyMuPDF 後全綠，代表那 15 紅是相依套件問題——**需要實機驗證**。
- **[E3] 材料資料撕裂實測**：`records/project_parts.json` 有 registered 20 筆 + custom 12 筆。其中 **11/20 個 registered id 不存在於 `material_pricebook.json`**（如 `PIPE-DN15-S10-304L`、`SUPPORT-01-2B-06A-01`），而修改單精靈的 `co_bridge.project_parts()` **只讀 pricebook**——這 11 筆在精靈裡看不到。同時 **18/20 個 registered id 無法從現行規則庫 `material_catalog_rules.py` 重建**（如 `BLF-DN50-CL150-CS` 用舊代碼 `CL150`，新規則產 `150`），證明料號編碼在兩次產生器改版間已經漂移。
- **[E4] 打包 spec 指向舊系統**：`packaging/IEC-site-change-manager.spec` 的 `Analysis` 入口是 `control/main.py`（PyQt6 舊 GUI），hiddenimports 是 PyQt6/win32com，`datas` **完全沒有** `co_main_web/`、`co_wizard_web/`、`records/material_catalog_rules.json`。照現在的 spec 打出來的 exe 是舊介面，新 HTML GUI 根本不在包裡。
- **[E5] 精靈啟動方式在 frozen 下必壞**：`co_main_bridge.open_wizard()` 用 `subprocess.Popen([sys.executable, "control/co_wizard_app.py"])`。打包後 `sys.executable` 是主 exe 而不是 python.exe，這行會變成「用主 exe 去執行一個 .py」→ 直接失敗。
- **[E6] 焊口跨單派號漏洞**：`change_order_builder._existing_ids()` = 管制表既有焊口 + **本張單**已加焊口；`co_bridge.export()` 出單後**不回寫管制表**，也**不讀同流水號歷史 change_order.json 的焊口碼**。→ 同一流水號開第二張單時，上一張派過的 `2a`、`1001` 會**再派一次**。舊 PyQt 精靈有 `_write_welds_to_control_table()` 回寫（`wizard.py:3163`），新管線沒有等價物。
- **[E7] records.json 已於 2026-07-09 清空**（`cleared_reason: "clear test record-management data"`，備份在 `.trash/`），主資料流已切到 `attachments/*/change_order.json` 掃描 + `weld_snapshot.json` 補舊資料（`co_main_bridge.records()/dates()`）。

---

## 1. 現況總結

一句話定位：**這是一套「現場修改單資料閉環」工具**——現場拍照 → 精靈建單（焊口編碼由引擎派發）→ `attachments/{單號}/change_order.json` 為единная 真相 → 主 GUI 管理/編輯 → 一鍵產出「業主資料包」（Excel 索引 + before/after/PDF 縮圖 + 相對路徑超連結）與開發檢查包。技術棧已從 PyQt6 遷移到 **Python + pywebview(WebView2) + 單檔 HTML/CSS/JS**，前後端走原生橋（非 HTTP）。

### 1.1 主 GUI（新版，`control/co_main_app.py` + `co_main_web/` + `co_main_bridge.py`）

- pywebview 啟動器 94 行、橋 1,873 行、前端單檔 index.html 3,031 行 + style.css 799 行。6 個分頁：**產出報告／紀錄管理／材料管理／請款追蹤／設定／健康**。
- 橋是 transport-agnostic 信封式（每個方法回 `{ok,data,error,trace}`），啟動器注入原生檔案/資料夾對話框；前端 `pywebviewready` 後用真資料覆蓋內建示範資料。
- 已接通的真功能：讀精靈草稿（掃 `attachments/**/change_order.json`）、日期樹（含 weld_snapshot 舊資料補位）、紀錄明細**可編輯回寫**（焊口/材料/照片，含 audit history append）、照片燈箱＋畫筆/箭頭標註存檔、取代/刪除照片、開資料夾/開 PDF、匯出紀錄清單與材料彙總 Excel、輸出中心（業主資料包/開發檢查包）、請款狀態儲存（`billing.json`，去金額只留狀態）、材料總庫（規則 lazy 查詢 + 分頁）、本案配件登記/自建/管架 BOM 展開、匯入管制單 Excel（4 種格式自動辨識）、設定頁（專案名、三個資料來源、輸出位置、**來源健康檢查**、**Excel 欄位映射預覽**）、健康頁（integrity_audit + project_guard 彙整）。

### 1.2 新修改單精靈（`co_wizard_app.py` + `co_wizard_web/` + `co_bridge.py` + 引擎五件組)

- 四步驟 app-shell（基本 → 焊口 → 照片圖面 → 材料）＋右側三段側欄（歷史／staging 收件匣／標註入口）。
- 焊口是**源頭驅動**：輸入流水號 → `existing_welds` 從焊口管制表載入該圖號真實焊口（`weld_lookup` 過濾 `屬性.1 ∈ {焊口, 管牙製作安裝}`）→ 點選加入「既有重焊」；新焊口自動帶最常見規格為預設。編碼由 `weld_codec` 派發：重焊 = base+a/b/c（第幾次重工）、新焊 = 1000+x 且過 `exists()` 防撞號。
- **無狀態重放**：前端任何變動都把完整 state 丟回 `build()`，後端用全新 builder replay 重算（編碼、狀態、缺漏），不留 stale state。
- 完整度 gating：`before + after + 圖面 PDF` 齊才准「正式建立」；存草稿不擋。出單走 `change_order_store.export_change_order`：建 `{attachments_root}/{series}_{date}_{NN}/`、複製照片改名 `before_n/after_n`、`drawing.pdf`、寫 `change_order.json`（檔案引用改相對名、原子寫入）。
- 標註是完整的一套：照片/PDF 均可（PDF 由 PyMuPDF 轉頁面圖、標完包回新 PDF 不動原圖），工具含畫筆/箭頭/框/圈/切除X/文字，顏色/線寬/字級可調，**常用文字 chips 會依「原因＋本單焊口碼」自動生成**（如「因現場管線干涉，切除原焊口 2，重焊 2a」）。
- 自動帶圖：依流水號從 `prefab_drawing_dir` 找對應 PDF（檔名前綴匹配 + 補零變體 + 深度/新舊排序）。

### 1.3 焊口表 / DWG LIST / PDF 圖面來源

- `weld_control.py`（1,559 行）：焊口管制表 Excel → JSON 快取（`.weld_cache`，mtime 驗證）、流水號索引 O(1) 查詢、工作表/表頭模糊匹配（同義字「焊/銲」、表頭可在第 1–12 列、NEW/OLD 工作表加減分）、批次回寫 Excel（舊精靈用）。
- `weld_lookup.py`：新引擎的唯讀查詢面（`lookup_spec/lookup_info/existing_weld_ids/exists`），`lookup_info` 額外帶 **DB數、預算編號、I.D**（多組欄名同義字）。
- DWG LIST：settings 動態欄位設定 + `record_manager.load_drawing_map()` 快取（舊鏈）；新設定頁有健康檢查與欄位預覽。
- 圖面 PDF：`prefab_drawing_dir` 資料夾掃描；來源健康檢查會算「流水號可匹配幾張 PDF」。

### 1.4 材料登記與本案配件

- **雙層模型**：總庫（母清單）＋本案配件（registered 子集 + custom 自建），全程**不算錢**（單價/金額已全面移除，meta 註明「價格交採購/會計」）。
- 總庫有兩個並存來源：① `records/material_pricebook.json`（16,887 筆、6.4MB，v4.0「標準總庫」，由 taxonomy 枚舉產生）② **規則庫 lazy 展開**（`material_catalog_rules.py` + `records/material_catalog_rules.json`：35 條規則 × taxonomy 軸，前端經 `material_catalog_summary/query` 分頁取用，不一次載入）。
- 自建材料受規則約束：`build_catalog_row()` 驗證零件模式（single/dual_schedule、olet、rating、bolt、fastener、u_bolt、support），**雙尺寸強制 尺寸1>尺寸2、單尺寸品項禁填尺寸2、材質必須在該類白名單**。
- 管架 Type 編碼展開：`support_bom.analyze_support_bom("01-2B-03C")` → BOM 材料列，一鍵登記＋加入紀錄材料明細。

### 1.5 照片與 PDF 標註

主 GUI 燈箱（畫筆/箭頭、`save_photo_annotation` 存 `_annotated.png` 並改指向）＋精靈完整標註模組（見 1.2）。輸出側另有 `pdf_overlay_renderer/pdf_overlay_schema`（normalized 座標、文字 shrink/wrap、表格分頁、圖片 cell）供現場摘要 PDF / 照片格 PDF。

### 1.6 業主資料包 / Excel 匯出

- `canonical_report.py`：把 records.json（舊）＋ `change_order.json`（新）＋資料夾實體收斂成 `report_set.v1`（含 aggregates、completeness、issues、provenance），**三層 fallback**：details → change_order → 資料夾 token。所有 renderer 吃這一份。
- `owner_data_report.py`：業主資料包 = 資料夾交付物（`owner_data_report/{單號}/before|after|pdf` + `owner_data_index.xlsx`）。索引 xlsx 三工作表（資料索引/焊口統計/用料統計）、品牌色表頭、斑馬紋、freeze+autofilter、**相對路徑超連結**（宣稱整包搬移可用）、before/after/PDF 縮圖卡（260×180 標題卡，PDF 先 poppler 後 PyMuPDF fallback，再退占位卡）、焊口列會 live 查管制表帶 尺寸/材質/厚度/DB/預算編號、新增/修改自動判別＋係數（新增 1、修改 1.5）。
- `site_statistics_exporter.py` + `site_output_runner.py`：開發檢查包（統計 xlsx、canonical_report_set.json、摘要/照片格 PDF 模板與渲染、marker 檔防誤覆寫）。
- 舊鏈（Excel COM 填 6-slot/27-slot xlsm 模板 → PDF）仍在（`excel_handler.py`、`main.py --cli`），與新鏈並存。

### 1.7 設定與資料來源健康狀態

- `settings.json`（meta.version 1.3、原子寫入、預設值 merge）＋ `records/app_settings.json`（新 GUI 覆蓋層）。
- 設定頁：專案名稱（會進報表標題）、DWG/焊口表/圖面資料夾 三張來源卡（狀態 pill + 健康摘要 + 「欄位」按鈕）、輸出位置、進階開關、「用途對照」表。
- **來源健康檢查**（`_excel_source_health`）：未設定/找不到/被 Excel 佔用（PermissionError→「被占用」）/找不到工作表（列出可用）/缺欄位（列出缺哪些）/成功（第幾列表頭、幾個欄位、欄名映射、有效資料筆數）。
- **Excel 欄位映射預覽**（`source_excel_preview` + 前端 `sourceSchemaModal`）：真的把來源 Excel 前 18 列×18 欄畫成格子，表頭列高亮，每欄有 checkbox 勾「這欄是流水號/焊口編號」——使用者在第 9 章問的「Excel 畫面＋打勾選欄位」**已經存在**，差的是入口的顯眼度與載入/錯誤狀態（見 §9）。

### 1.8 測試覆蓋概況

- `tests/` 共 76 檔。覆蓋面很廣：引擎五件組（change_order/builder/store/codec/lookup）、兩座橋（test_co_bridge 、test_co_main_bridge +252 行未 commit 新增）、canonical_report、owner_data_report（+137 行新增）、site 統計/輸出中心、PDF overlay schema/renderer、材料（constants/pricebook/importer/repricing/audit/taxonomy 相關）、billing 狀態機、release 工程（build/check/smoke 工具）、import guard（擋 COM 依賴外洩）、packaging spec 檢查。
- 沙箱實跑：447 綠[E2]。**弱區**：新前端（兩個 index.html 共 4,710 行 JS/HTML）零自動化測試；`weld_control` 的 Excel 回寫路徑無表頭不在第 1 列的測試；多人並發/檔案鎖零測試；`test_material_catalog_generator.py` 已與未 commit 重寫脫鉤（收集失敗）。

---

## 2. 目前最像企業級工具的地方

不客氣的審查也要先把功勞記清楚——以下這些設計已經是企業級水準，施工時**不要動壞它們**：

1. **Canonical 資料模型放在正確的位置**（`change_order.py`）：schema_version 從第一天就有（0.2）、Enum 序列化成 value、反序列化**容忍未知欄位/未知 Enum 值**（前向相容）、audit 是可累加的 `history[]` 而非單一時間戳、`save_json` 原子寫入。「精靈收集的＝檔案格式＝未來 DB 表」這個定位完全正確，UI 是可丟的下游。
2. **編碼引擎與 IO 徹底分離**：`weld_codec` 是純函式（parse/next_rework/next_new/assign_event，「字母＝第幾次重工、與操作無關」的領域規則被正確編碼）、`weld_lookup` 唯讀包裝、`change_order_builder` headless 可測、`change_order_store` 只管落地。這一層在沙箱不接 GUI 全部可測，正是能長成中央服務的骨架。
3. **橋的信封紀律**：兩座橋所有對外方法統一 `{ok,data,error,trace}`，例外永不外洩到前端；檔案對話框用注入；`build()` 無狀態重放。未來包成 FastAPI route 簽名一行不用改——這是全 repo 最有遠見的設計。
4. **來源容錯是「工地等級」的**：欄名同義字（焊/銲、NO/流水號/ISO流編）、表頭可在第 1–12 列、工作表名模糊匹配＋NEW/OLD 加減分、PermissionError 翻成「檔案可能正由 Excel 開啟」、找不到工作表時列出可用清單。這些是真的被現場檔案折磨過才會寫出來的防禦。
5. **設定頁的來源健康檢查 + Excel 欄位映射預覽**（§1.7）：把「設定對不對」變成看得到的狀態，而不是等匯出爆炸。多數內部工具到產品化後期才補這個，這裡已經有了。
6. **業主資料包的交付物思維**：整包資料夾 + 相對路徑超連結 + 縮圖卡（含 PDF 首頁渲染的雙 fallback + 占位卡）+ 封面使用說明文字。輸出中心 marker 檔（`.iec_site_output_center`）防止 overwrite 誤刪非輸出資料夾（`_reset_child_dir` 還檢查父目錄）——防呆意識很好。
7. **release 工程雛形已超前多數內部工具**：`build_release.py` 產 `build_info.json`（git commit / dirty 記號）→ `check_release_package.py` 驗包（拒絕 stale commit、拒絕頂層夾帶專案資料、資產齊全性）→ packaged CLI smoke → zip + sha256。還有 `--health-check` 啟動守門、`windows_version_info.txt` 檔案屬性。
8. **啟動守門與健康體檢**：`project_guard`（GuardResult/StartupDecision/auto-repair 區分 blocking 與可自動修復）、`integrity_audit`（records ↔ attachments ↔ billing 參照完整性）、`diagnostics.collect_support_bundle`（支援診斷包）、`operation_journal`（當機復原日誌）。企業導入最怕的「壞了說不清」已有骨架。
9. **材料的「規則生成 + 受控自建」方向**：不持久化 16,887 列全枚舉、以 35 條規則 lazy 展開＋分頁查詢；自建材料走 `build_catalog_row` 硬驗證（雙尺寸大小關係、白名單材質、單尺寸禁填尺寸2）。這正是防「亂填」的正確架構（剩下的問題是新舊兩軌並存與 id 漂移，見 §3/§7）。
10. **測試文化與工程紀律**：76 個測試檔、import guard 擋 COM 污染、`.gitattributes` 鎖行尾、`.githooks`、pre-commit 安裝腳本、`docs/00_big_bang_產品進化總控室/` 70+ 篇決策與回補紀錄——知識沒有只活在人腦裡。

---

## 3. 目前還不像企業級工具的地方

分級定義：**P0＝封裝 exe 前必修**（不修，exe 交出去會直接出事或根本不能用）；**P1＝短期應修**（明顯提升可靠性）；**P2＝中期優化**（維護性/擴充性）；**P3＝長期產品化**。

### P0-1 打包 spec 打的是舊系統，新 GUI 不在包裡

- **問題**：`packaging/IEC-site-change-manager.spec` 入口 `control/main.py`（PyQt6），hiddenimports 全是 PyQt6/win32com；`datas` 沒有 `co_main_web/`、`co_wizard_web/`、`records/material_catalog_rules.json`、部分 `records/seed`。[E4]
- **風險**：照現行流程 build 出來的 exe 是舊介面；就算把入口改掉，前端 HTML/圖片沒進 datas，開窗即白畫面；pywebview 在 Windows 依賴 pythonnet/clr-loader 與 `webview.platforms.*`，PyInstaller 不宣告 hiddenimports 會在使用者機器上 ImportError。
- **涉及檔案**：`packaging/IEC-site-change-manager.spec`、`tools/build_release.py`（DEFAULT_SPEC）、`packaging/README.md`、`tools/check_release_package.py`（資產清單）、`packaging/自動Build.bat`。
- **建議作法**：新增 `packaging/IEC-site-change-manager-web.spec`（或改造現 spec）：入口改 `control/co_main_app.py`；datas 加 `control/co_main_web`→`control/co_main_web`、`control/co_wizard_web`→`control/co_wizard_web`、`records/material_taxonomy.json`、`records/material_catalog_rules.json`、`records/seed/`、`template/`；hiddenimports 換成 `webview`, `webview.platforms.winforms`, `webview.platforms.edgechromium`, `clr_loader`, `pythonnet`（實際清單以 spike 為準——**需要實機驗證**）；PyQt6 從 hiddenimports 移除、加入 excludes 以縮包。`check_release_package.py` 的必備資產清單同步加 `co_main_web/index.html` 等。
- **驗收標準**：乾淨機器（無 Python）上解壓 onedir zip → 雙擊 exe → 新版主 GUI 開窗、六分頁可切、材料總庫查得到、健康頁能跑；`tools/check_release_package.py` 綠燈。

### P0-2 精靈啟動在 frozen 下必壞

- **問題**：`co_main_bridge.open_wizard()` 用 `subprocess.Popen([sys.executable, str(co_wizard_app.py)])`。[E5]
- **風險**：exe 版按「修改單精靈」毫無反應或跳錯，等於閹掉核心建單流程。
- **涉及檔案**：`control/co_main_bridge.py`（open_wizard）、`control/co_main_app.py`、`control/co_wizard_app.py`、新 spec。
- **建議作法**（擇一，建議 a）：
  a. **單 exe 多入口**：主入口 `co_main_app.py` 加 argv 分流——`IEC-xxx.exe --wizard` 時改跑 wizard 視窗；`open_wizard()` 判斷 `getattr(sys,"frozen",False)` 時改 `Popen([sys.executable, "--wizard"])`，非 frozen 保持現行為。
  b. 同進程開第二個 `webview.create_window`（要驗證 pywebview 多視窗 + 各自 js_api 的穩定性——**需要實機驗證**）。
- **驗收標準**：dev 模式與 exe 模式各按一次「修改單精靈」，都能開窗、載焊口、出單；出單後主 GUI 紀錄頁刷新看得到新單。

### P0-3 焊口跨單派號會重號（領域正確性）

- **問題**：同一流水號第二張修改單不知道第一張派過什麼碼。[E6] `next_rework("2", ids)` 的 ids 只含管制表 + 本單 → 第一張派了 `2a` 且尚未有人手動更新管制表時，第二張又派 `2a`；`next_new` 同理重派 `1001`。舊精靈的管制表回寫（auto_sync）在新管線中沒有等價物，settings 的 `weld_control.auto_sync: true` 目前對新精靈是死設定。
- **風險**：焊口碼是對業主的追溯主鍵；重號＝計量錯、RT 報驗錯、業主信任毀損。這是全案最嚴重的領域級 bug。
- **涉及檔案**：`control/change_order_builder.py`（`_existing_ids`）、`control/co_bridge.py`（`_build_co`/`export`）、`control/change_order_store.py`、`tests/test_change_order_builder.py`、`tests/test_co_bridge.py`。
- **建議作法**：兩層防護——
  1. **先做（純讀、無鎖需求）**：builder 增加 `history_codes: Iterable[str]` 注入；`co_bridge._build_co` 出於同 series 掃 `attachments_root` 下 `{series}_*/change_order.json` 收集所有 `welds[].code`（與 `base+rework_index` 推出的字母序），併入 `_existing_ids`。歷史掃描已有現成邏輯（`co_bridge.history`）可重用。
  2. **後做（P1，要配檔案鎖）**：正式建立成功後回寫管制表（重用 `weld_control.add_welds_batch`，先修 P1-1 表頭列 bug），寫失敗不擋出單、記入 audit 與健康頁待辦。
- **驗收標準**：新測試——同 series 先 export 一張含 `2a`、`1001` 的單，再 build 第二張加入既有焊口 2 與一口新焊 → 必須得到 `2b`、`1002`。跑 `pytest tests/test_change_order_builder.py tests/test_co_bridge.py`。

### P0-4 寫入原子性不一致＋雲端共用資料夾零檔案鎖

- **問題**：`settings_manager` 與 `change_order.save_json` 有原子寫，但 `co_main_bridge.py` 有 **8 處裸 `write_text`**：`_write_change_order`（紀錄編輯回寫！）、`save_billing`、`_write_project_parts_doc`、`_write_settings_section/_project_name/_path`、`import_material_excel` 寫 6.4MB pricebook、`save_setting`。部署前提是「雲端共用資料夾多人輪流」（H:\共用雲端硬碟），無任何 lockfile/writer 心跳。
- **風險**：寫到一半（同步軟體搬檔、當機、兩人同開）→ JSON 半截毀損；Google Drive 桌面端對「兩端同改」會長出 conflict 副本，程式只讀原名檔 → 無聲丟另一人的修改。這是記憶中列的「最危險地雷 #1」，至今仍在。
- **涉及檔案**：`control/co_main_bridge.py`（統一收斂寫入）、`control/project_guard.py`（已有 `atomic_write_json` 可重用）、`control/co_bridge.py`（`save_annotated` 等 write_bytes 可接受，但 change_order 相關要原子）。
- **建議作法**：P0 範圍先做**原子化**：抽 `control/json_store.py`（`read_json/write_json_atomic(path, data)`，內部 `.tmp` + `os.replace`，統一 utf-8-sig 讀），把 8 處裸寫全部換掉；順手把 `_read_json` 三份重複實作（co_main_bridge/co_bridge/canonical_report）收斂進來。**單寫者鎖（lockfile + 過期心跳 + UI「目前由 ○○○ 使用中」）列 P1-2**，因為要設計搶鎖 UX。
- **驗收標準**：`grep -n "write_text" control/co_main_bridge.py` 只剩經由 json_store 的呼叫；kill -9 練習（寫入中殺進程）後 JSON 仍可解析；新增 `tests/test_json_store.py`。

### P0-5 後端未連線時前端顯示「像真的」假資料

- **問題**：`co_main_web/index.html` 內建示範資料——4 筆假紀錄（WELD_POOL/MAT_POOL 還帶著已被移除的 price/amount 欄位）、假請款 BILL、假批次 `BATCHES`（**硬編「台積電 F18」**）、假 PRICE 10 筆、健康頁 HTML 裡寫死 3 列假 issues 與假統計。`pywebviewready` 後才用真資料覆蓋；橋若失敗只有一顆 toast，畫面繼續呈現假資料。
- **風險**：exe 在 WebView2 缺失/橋掛掉時，使用者看到的是一套「看起來能用」的假系統，會做出真決策；給長官展示時被問「台積電 F18 是什麼」更是災難。
- **涉及檔案**：`control/co_main_web/index.html`（records/BILL/BATCHES/PRICE/健康 tab 靜態列、`money()` 等殘留）、`control/co_main_bridge.py`（無 ping 之外的連線態）。
- **建議作法**：把所有示範資料改為空陣列＋各分頁空狀態（已有 `emptyBlock`/插畫可重用）；新增全域連線橫幅——`pywebviewready` 未在 N 秒內發生或 `info()` 失敗時，頂部出紅條「未連線到後端，資料不可用」，各分頁顯示錯誤狀態而非假資料；刪掉 `money()`、WELD_POOL 的價格欄位、台積電字樣。若要保留 demo 模式，做成 `?demo=1` 顯式參數。
- **驗收標準**：直接用瀏覽器開 `index.html`（無 pywebview）→ 每個分頁都是空/未連線狀態，找不到任何假紀錄與「台積電」字樣；桌面模式行為不變。

### P0-6 settings.json 的「repo 模板」與「本機實例」混在同一檔

- **問題**：`settings.json` 被 git 追蹤，內容卻是**這台機器**的 H:\ 絕對路徑、`last_browse_dir`、`meta.last_modified`（每存一次設定就髒一次 git）[E1]。另外 `records/records.json`、`records/material_taxonomy.json`、`records/material_pricebook.json`(6.4MB) 也被追蹤，但其中 records.json 是 runtime 資料（已被今天的清空操作證明 [E7]）。
- **風險**：exe 部署後每個案場/每台機器的路徑不同；git pull 會互相覆蓋彼此設定；打包時把個人路徑燒進交付物。
- **涉及檔案**：`settings.json`、`.gitignore`、`control/settings_manager.py`、`control/project_guard.py`（首啟建檔已有 `_default_settings()`）、`tools/check_release_package.py`（已會擋頂層專案資料——方向一致）。
- **建議作法**：repo 只留 `settings.template.json`（空路徑），`.gitignore` 加 `settings.json`；`settings_manager._load()` 找不到 settings.json 時從 template 複製（project_guard 首啟守門已有類似機制，收斂到一處）；`records.json` 移出追蹤（`git rm --cached` + ignore），pricebook/taxonomy/rules 屬「標準模板」留在 repo（見 §5 分類）。
- **驗收標準**：clone 全新 repo → 首啟自動生成本機 settings.json；改設定後 `git status` 乾淨；打包產物內不含任何 `H:\` 或使用者名稱字串（可 grep 驗證）。

### P0-7 未 commit 的 2,900 行改動 + 已知壞測試，缺封裝基準線

- **問題**：24 檔未 commit（含本次要打包的核心：橋、前端、owner report）[E1]；`tests/test_material_catalog_generator.py` 對未 commit 的工具重寫已 ImportError [E2]；無 CI，「全套測試在哪個 commit 是綠的」目前答不出來。
- **風險**：打包的 exe 對不回原始碼版本；`build_release.py` 會標 `source_dirty: true`，`check_release_package` 預設直接拒收——現在的工作區根本過不了自家的 release gate。
- **涉及檔案**：整個工作區、`tests/test_material_catalog_generator.py`、`tools/generate_material_catalog.py`、`.githooks/`。
- **建議作法**：①把現行工作區切成 3–5 個語意 commit（材料規則庫、owner report 強化、設定來源預覽、精靈調整、settings/records 資料變動分開）②修或重寫 `test_material_catalog_generator.py` 對準新工具介面（測 `write_rules` 產出的 JSON schema 與 `--expanded` 稽核輸出）③在 Windows 實機跑全套 pytest 記錄基準（處理歷史 15 紅：裝齊 PyMuPDF 相依或標 `@pytest.mark.skipif` 註明原因——**需要實機驗證**）④哪怕沒有 CI 伺服器，先在 `.githooks/pre-push` 跑 `pytest -q`。
- **驗收標準**：`git status --short` 乾淨；`python -m pytest -q` 在 Windows 全綠（或 skip 均有註記原因）；`tools/build_release.py --skip-build` 的 package gate 能過 dirty 檢查。

### P1-1 管制表回寫假設表頭在第 1 列（寫入路徑與讀取路徑不對稱）

- **問題**：`weld_control._load_from_excel` 能在第 1–12 列找表頭，但 `add_weld`/`add_welds_batch` 寫入時 `headers = [cell.value for cell in ws[1]]`——表頭若在第 2+ 列（實際管制表常有大標題列），col_map 建在標題列上 → `resolve_col` 對不到 → **欄位無聲漏寫**或寫錯欄。
- **風險**：補登/回寫功能在真實表上靜默毀資料；P0-3 之後若開啟回寫，此 bug 會被放大。
- **涉及檔案**：`control/weld_control.py`（add_weld / add_welds_batch）、`tests/`（新增表頭在第 3 列的 fixture）。
- **建議作法**：寫入前呼叫 `_resolve_sheet_and_header(wb)` 拿 `_header_row/_col_map` 再定位；`next_row = ws.max_row + 1` 也要防表尾有合計列（先掃到最後一個主鍵非空列）。`add_weld` 順便補上 `resolve_col`（現在只有 batch 有模糊匹配，單筆是精確匹配——行為不一致）。
- **驗收標準**：新測試——表頭在第 3 列、欄名用「銲口編號」的假表，批次寫入後重讀，所有動態欄位落在正確欄。

### P1-2 雲端共用資料夾單寫者鎖（P0-4 的第二階段）

- **問題/風險**：同 P0-4；原子寫只保護「單機當機」，擋不住兩人同時編同一張單、同時存 billing。
- **涉及檔案**：新 `control/project_lock.py`、`co_main_app.py`/`co_wizard_app.py` 啟動時取鎖、`co_main_web` 頂欄顯示鎖狀態。
- **建議作法**：專案根目錄 `.project.lock`（.gitignore 已有此名——之前已有此構想）記 `{user, host, pid, heartbeat_at}`；啟動取鎖、每 30s 心跳、逾 2 分鐘視為殭屍鎖可搶；唯讀模式開關（搶不到鎖仍可看、不可寫）。Google Drive 的鎖檔同步延遲要實測——**需要實機驗證**（兩台機器同開的實際行為）。
- **驗收標準**：兩個進程同開：第二個進到唯讀模式並顯示占用者；殺掉第一個 2 分鐘後第二個可接手；單元測試模擬殭屍鎖。

### P1-3 材料資料撕裂：精靈看不到本案配件的一半（實測 11/20）

- **問題**：主 GUI 的料號解析鏈是「規則庫 rows_by_ids → legacy pricebook → custom」三層（`co_main_bridge._material_items_for_ids`），精靈的 `co_bridge.project_parts()` 卻只讀 pricebook items ∩ registered——規則生成 id 與 custom（管架展開）全部漏掉。[E3]
- **風險**：現場在精靈選料時找不到內業登記好的料 → 改走「待登記材料」手填 → 資料再度撕裂，雙層模型形同虛設。
- **涉及檔案**：`control/co_bridge.py`（`project_parts/_read_material_items/_read_project_part_ids`）、`control/co_main_bridge.py`（把解析鏈抽出）、新 `control/material_resolver.py`、`tests/test_co_bridge.py`。
- **建議作法**：抽 `material_resolver.resolve_ids(root, ids) -> list[frontend_row]`（內容＝現在 `_material_items_for_ids` 的三層邏輯），兩座橋共用；`co_bridge.project_parts()` 改呼叫它並回 custom。
- **驗收標準**：以 [E3] 的真實 project_parts.json 為 fixture，`co_bridge.project_parts()` 回滿 20 筆（含 SUPPORT-* custom）；兩座橋回的同 id 資料列欄位一致。

### P1-4 材料料號不穩定：規則改版讓舊註冊變孤兒，且會被無聲刪除

- **問題**：料號由規則前綴+尺寸+SCH+材質代碼拼成，但代碼函數已漂移過（`CL150`→`150`、`SS`↔`304`），實測 18/20 registered 無法從現行規則重建 [E3]；更糟的是 `co_main_bridge.project_parts()` 會把解析不到的 id **自動從 registered 移除**（`dropped` 直接寫回）——規則改版＝使用者登記無聲蒸發。
- **風險**：料號會進 `change_order.json.materials[].component_id` 與匯出 Excel——歷史單據的料號從此對不回總庫。
- **涉及檔案**：`control/material_catalog_rules.py`（`_code`）、`control/co_main_bridge.py`（project_parts 的 dropped 邏輯）、`records/material_catalog_rules.json`（加 id_scheme 版本欄）、新 migration。
- **建議作法**：①宣告 **id 編碼凍結**：`_code()` 的映射表版本化（`id_scheme: "v1"` 寫進 rules json），任何改動必須附 `records/migrations/material_id_v1_to_v2.json` 對照表並提供重寫 project_parts/change_order 的工具 ②`project_parts()` 停止自動刪 dropped——改回傳 `unresolved` 清單，前端顯示「N 筆料號待遷移」黃條 ③補一次性修復腳本把現存 20 筆對回現行規則（`CL150→150` 等）。
- **驗收標準**：規則檔亂改 prefix 後，registered 筆數不變、UI 出現待遷移提示；migration 腳本跑完 [E3] 的 18 筆全部可解析。

### P1-5 紀錄編輯以「列索引」對齊舊資料，刪列/換序會錯位 canonical 欄位

- **問題**：`co_main_bridge.save_record()` 用 `old_welds[i]` 位置對齊來保留 `origin/joint_type/base/rework_index` 等前端沒有的欄位——在主 GUI 刪掉第 1 列焊口後儲存，第 2 列的 canonical 欄位會嫁接到別列上。
- **風險**：`origin/base` 錯位 → 匯出的「新增/修改」判別與係數跟著錯 → 業主報表錯。
- **涉及檔案**：`control/co_main_bridge.py`（save_record）、`control/co_main_web/index.html`（rec 明細表把隱藏欄帶回）、`tests/test_co_main_bridge.py`。
- **建議作法**：前端列資料帶回穩定 key（現成的 `code`；或送 `_orig_index`），後端以 key 對齊；找不到 key 視為新列（origin=manual）。刪列行為加測試。
- **驗收標準**：測試——三口焊口刪第一口再存，第二、三口的 origin/base/joint_type 不變。

### P1-6 快取寫進雲端共用資料夾

- **問題**：`weld_control` 的 JSON 快取寫在**管制表所在目錄**（`H:\...\03.銲口管制\.weld_cache\`）。
- **風險**：污染業主/公司共用區、同步流量、多人互踩快取、共用區唯讀時快取直接失效還每次重讀 Excel。
- **涉及檔案**：`control/weld_control.py`（`_get_cache_dir`）。
- **建議作法**：快取改本機 `%LOCALAPPDATA%\IEC-site-change-manager\weld_cache\`（沿用「路徑 hash + sheet」檔名即可區分不同來源檔）；保留舊位置讀取 fallback 一版後移除。
- **驗收標準**：跑一次載入後 H: 目錄不再新增 `.weld_cache`；本機快取命中率 log 可見；共用區唯讀情境仍可用（**需要實機驗證**）。

### P1-7 健康檢查自己吞例外

- **問題**：`co_main_bridge.health()` 對 `integrity_audit`/`project_guard` 各包 `except Exception: pass`——體檢器本身壞掉時回「正常：未發現問題」。
- **風險**：最需要可信度的頁面給出假綠燈。
- **涉及檔案**：`control/co_main_bridge.py`（health、_issue_dict）。
- **建議作法**：except 改為塞入一筆 `{"source":"健康檢查","level":"error","title":"稽核器執行失敗","message":str(exc)}`；同時整體狀態至少 warn。
- **驗收標準**：monkeypatch 讓 audit_integrity 拋錯 → health() 回 err 且 issues 含執行失敗項。

### P1-8 寫死的前案殘留與寫死的計費係數

- **問題**：①`owner_data_report._owner_project_name()` 專案名 fallback 寫死 `"HP6精濾區配管工事"` ②`settings_manager.get_drawing_list_path()` 自動搜尋寫死 `可寧衛_DRAWING LIST*.xlsm`（上上個案場）③新增/修改係數 1 / 1.5 寫死在 `_weld_change_factor`④`control/wizard_data.json` 是舊案語句庫、新精靈的常用原因又硬編在 index.html `<optgroup>`——兩套語句庫不同步。
- **風險**：換案場交付的報表標題/係數錯；殘留字樣讓業主看見別案名稱。
- **涉及檔案**：`control/owner_data_report.py`、`control/settings_manager.py`、`control/co_wizard_web/index.html`、`control/wizard_data.json`。
- **建議作法**：專案名 fallback 改空字串＋在索引表頭顯示「（未設定專案名稱）」提醒；刪可寧衛 glob（回空讓使用者設定）；係數移入 settings 新 section `weld_billing: {new_factor: 1, rework_factor: 1.5}` 並在設定頁顯示；常用原因收斂到單一 JSON（`records/reason_presets.json` 或沿用 wizard_data.json）由橋提供。
- **驗收標準**：grep 不到 `HP6精濾區`、`可寧衛` 於 control/；改設定係數後焊口統計表跟著變。

### P1-9 統一日誌：print 進了看不見的黑洞

- **問題**：`log_config.py` 有完整 rotating file 架構，但整條新鏈（weld_control 的 ✅/❌ print、兩座橋、pywebview 啟動器）都用 `print()`。exe（尤其未來 `console=False`）之後 stdout 無處去。
- **風險**：現場出問題只剩「不能用」三個字，支援診斷包（diagnostics）收不到新鏈的痕跡。
- **涉及檔案**：`control/weld_control.py`、`control/co_main_bridge.py`、`control/co_bridge.py`、`control/co_main_app.py`、`control/co_wizard_app.py`、`control/log_config.py`。
- **建議作法**：兩個 launcher 開頭呼叫 `setup_logging()`；print 全換 `logger.info/warning/error`；橋的 `_enveloped` 在 except 分支加 `logger.exception(fn.__name__)`（trace 已回前端，也要落地）。
- **驗收標準**：跑一次主 GUI 操作後 `logs/` 有當日檔且含橋呼叫紀錄；`grep -n "print(" control/co_main_bridge.py control/co_bridge.py control/weld_control.py` 歸零（測試/工具腳本除外）。

### P1-10 請款分頁的死按鈕與半接線流程

- **問題**：「匯出報表」「請款單」兩顆按鈕**沒有 onclick**（純皮）；「建立批次/更新批次狀態」按了只 toast「尚未接入」；`billing_batch.py`/`billing_status.py`（含狀態機驗證）後端存在但沒接。健康頁「修復」「診斷包」同樣 toast 未接（而 `project_guard.auto-repair`、`diagnostics.collect_support_bundle` 後端都在）。
- **風險**：展示時被點到就穿幫；使用者以為存了什麼其實沒有。
- **涉及檔案**：`control/co_main_web/index.html`、`control/co_main_bridge.py`（補 bridge 方法）、`control/billing_batch.py`、`control/diagnostics.py`、`control/project_guard.py`。
- **建議作法**：短期（封裝前）——沒接的按鈕一律**移除或 disabled + tooltip「規劃中」**，不准有按了沒反應的活按鈕；中期——接上既有後端：`export_billing_report()`（沿 `_export_rows` 模式）、健康「修復」→ `project_guard` auto-repair、「支援診斷包」→ `collect_support_bundle` 後開資料夾。
- **驗收標準**：UI 走查清單（見 §9）零死按鈕；修復按鈕能建出缺少的 output/ 目錄並刷新健康頁。

### P2-1 co_main_bridge 神類與 3,031 行單檔前端

- **問題**：橋 1,873 行 40+ 方法混雜（材料/紀錄/請款/設定/輸出/健康）；前端單檔 index.html HTML+CSS+JS 全塞（3,031 行），無模組、無建置、無 lint。
- **風險**：改一處掃全檔；多人協作必衝突；AI 施工誤傷半徑大。
- **涉及檔案**：`control/co_main_bridge.py`、`control/co_main_web/index.html`。
- **建議作法**：橋拆薄殼＋服務：`MainBridge` 只留信封與注入，邏輯移 `services/records_service.py`、`materials_service.py`、`settings_service.py`、`output_service.py`（信封簽名不變，測試照跑）；前端至少拆 `app.js`/`records.js`/`materials.js`/`billing.js`/`settings.js`＋沿用既有 style.css（精靈已示範過抽 css）。不引入打包器，保持 file:// 可載入的 `<script src>` 順序即可。
- **驗收標準**：test_co_main_bridge 全綠不改斷言；index.html 降到 <800 行；每個 js 檔 <600 行。

### P2-2 records 資料層缺 schema version 與 migration 通道（詳見 §5）

- **問題**：`change_order.json` 有 schema_version，但 `project_parts.json`、`billing.json`、`app_settings.json`、`weld_snapshot.json` 都沒有；settings 的 `_merge_defaults` 只做 shallow merge（巢狀新增鍵會補、但改結構就沒轍），meta.version 1.3 沒有任何讀取端判斷。
- **建議作法/驗收**：見 §5.4/§5.5。

### P2-3 每次操作全樹重掃 change_order.json

- **問題**：`records()/dates()/billing()/_find_change_order()` 每呼叫都 `rglob` 全 attachments 並解析所有 JSON；`_find_change_order` 更是每次照片操作都全掃。
- **風險**：單量到數百張＋H: 網路磁碟時，每個點擊都是一次全樹網路 IO；`_source_health` 還會在讀設定頁時掃一次。
- **建議作法**：橋內建 in-memory index（path→id/mtime），以資料夾 mtime 增量刷新；`_find_change_order` 先查 index。目標單機 500 單 <300ms。
- **涉及檔案**：`control/co_main_bridge.py`。
- **驗收標準**：造 500 個假單資料夾的 perf 測試，records() 第二次呼叫 <300ms（**H: 上的表現需要實機驗證**）。

### P2-4 image_data_url 全檔 base64 過橋

- **問題**：燈箱/縮圖把整張圖 base64 進 JS（1280px 預處理後尚可，但 staging 原始照片與 PDF 高倍渲染會到數 MB/張），紀錄明細一次 hydrate 全部照片。
- **建議作法**：`image_data_url` 加 `max_edge` 參數（縮圖 320/燈箱 1600，Pillow 現場縮）；hydrate 改可視區 lazy。
- **涉及檔案**：`control/co_main_bridge.py`、`control/co_bridge.py`、前端 hydrate 邏輯。
- **驗收標準**：10MB 原圖的縮圖請求回應 payload <200KB。

### P2-5 舊 PyQt 鏈與新鏈長期並存無退場計畫

- **問題**：`gui.py/gui_panels.py(205KB)/gui_dialogs.py/wizard.py/theme.py` 與 Excel COM 鏈仍在 control/，`main.py` 仍是它們的入口；PROJECT_MAP.md/DATA_FLOW_AUDIT.md 還在描述 3 月的 PyQt 世界（文件已失真）。
- **建議作法**：明確宣告「維護模式」：`legacy/` 子資料夾或至少檔頭標註；PROJECT_MAP.md 重寫成新架構（或標「歷史文件」）；xlsm COM 產單若仍是交付必需品，把它接進新 GUI 的輸出中心選項，否則列退役時程。
- **驗收標準**：新進者只讀 README+PROJECT_MAP 能找到正確入口；docs 無自相矛盾。

### P2-6 audit 有軌跡、無人名

- **問題**：`AuditEntry.who` 永遠 None；多人共用下「誰改的」答不出來。
- **建議作法**：settings 加 `user.display_name`（首啟問一次，預設 `getpass.getuser()`）；橋寫 audit/journal 時帶入；業主資料包不輸出人名（內部才看）。
- **涉及檔案**：`control/settings_manager.py`、`control/co_main_bridge.py`（save_record 等）、`control/change_order_builder.py`。
- **驗收標準**：兩台機器各改一單，audit history 分得出誰是誰。

### P3-1 中央化路徑（資料軸）

橋已 transport-agnostic，正確的長線是：`services/` 抽乾淨（P2-1）→ 同一批服務包 FastAPI → SQLite/PostgreSQL 落 `change_order`（schema 即 `change_order.py`）→ 桌面版切「本機模式/伺服器模式」。不要在資料夾共用模式上繼續加高級功能（請款批次多人流程等），那些天生需要 DB。

### P3-2 更新機制與版本回報

exe 版本已進 `app_info/build_info`；長期補：啟動時讀共用區 `latest_version.json` 提示更新、健康頁顯示 build 資訊、診斷包自動夾 build_info。

### P3-3 權限與簽核流

`Authorization` 欄位已預留（業主簽認選填/案場可升必填）；產品化時補：每案必填矩陣設定頁、簽認證據影像流程、修改單狀態機（草稿→待簽→定稿→已請款鎖定——billing_status 已有鎖定概念可銜接）。

---

## 4. 封裝成 EXE 前檢查清單

### 4.1 pywebview / WebView2 依賴

- [ ] **先跑 packaging spike 再全押**（docs 技術路線決策也是這麼寫的）：最小 pywebview 視窗 + PyInstaller onedir，丟到「沒裝過開發工具的公司機器」跑。重點驗證 pythonnet/clr-loader 在 frozen 下載入（pywebview Windows 後端）。**需要實機驗證**。
- [ ] hiddenimports 至少涵蓋：`webview.platforms.winforms`、`webview.platforms.edgechromium`、`clr_loader.ffi`、`pythonnet`；datas 帶 `webview` 的 js 資源（pyinstaller hook 多半會處理，spike 確認）。
- [ ] WebView2 Runtime 檢測：`co_main_app` 已有失敗提示文字；exe 版要升級成 **MessageBox＋自動開啟微軟下載頁**（console=False 之後 print 沒人看得到），或交付包直接附 Evergreen Bootstrapper（~2MB）由啟動 bat 先裝。
- [ ] Win10 舊機沒有內建 WebView2——公司機器盤點一輪。**需要實機驗證**。

### 4.2 Python runtime / 封裝策略

- [ ] 維持 **PyInstaller onedir**（README 現行策略正確；onefile 啟動慢、殺毒誤判高、_MEIPASS 臨時目錄在受控電腦常被擋）。
- [ ] **UPX 建議關閉**（spec 目前 `upx=True`）：公司防毒對 UPX 壓縮的 exe 誤判率高，體積換客訴不划算。
- [ ] `console=True` 先保留一版（診斷友善），穩定後出第二個 windowed 入口。
- [ ] 移除 PyQt6/win32com hiddenimports（新入口用不到，白白 +80MB）；若 xlsm COM 舊鏈要一起出貨，改為兩支 exe 或延用舊 spec 另打。
- [ ] 版本資訊（`windows_version_info.txt`）版本號與 `app_info.py`、build_info 三處一致化（單一來源生成）。
- [ ] 簽章：短期沒有 code signing 憑證的話，交付文件註明 SmartScreen「其他資訊→仍要執行」步驟；中期買 OV 憑證。

### 4.3 assets / img / records / settings.json 路徑策略

- [ ] datas 必帶：`control/co_main_web/**`（index/style/img 含 parts 縮圖 32 張）、`control/co_wizard_web/**`、`template/*.xlsm`、`records/material_taxonomy.json`、`records/material_catalog_rules.json`、`records/seed/**`、`control/wizard_data.json`、`packaging/generated/build_info.json`。
- [ ] `resources.py` 已正確二分：**resource_dir**（frozen＝`_MEIPASS`/onedir 的 `_internal`，唯讀）vs **project_dir**（frozen＝exe 所在資料夾，讀寫）。守住紀律：**模板/規則/圖示走 resource_path，一切會寫的走 project_path**。
- [ ] 逐一審 `Path(__file__)` 相對定位：`co_main_app._INDEX`、`co_wizard_app._INDEX`（frozen 下 `__file__` 在 `_internal`，datas 目的路徑要對齊 `control/co_main_web`）；`co_bridge.records_dir` 的 `Path(__file__).parents[1]/records` 與 `_staging_root()` fallback；`material_taxonomy._candidate_paths` 第三候選。建議統一改走 `resources.resource_path/project_path`。
- [ ] `ChangeOrderBridge` 預設 `Path.cwd()/change_order_records` 這個 cwd fallback 要刪（雙擊 exe 的 cwd 不可控）；launcher 已顯式傳入，保底也應改 project_path。
- [ ] 打包產物 grep 驗證：不含 `H:\`、使用者名、`HP6`、`可寧衛`。

### 4.4 使用者資料、設定、快取放哪裡

建議三層（並寫進 §5 的治理表）：

| 類別 | 位置 | 內容 |
|---|---|---|
| 程式資源（唯讀） | onedir `_internal/` | 前端、模板、taxonomy/rules 種子 |
| 專案資料（共用） | 「專案資料夾」＝使用者選定（可在 H:）| attachments/、records/*.json、settings.json、output/、logs/（專案事件） |
| 本機快取/日誌 | `%LOCALAPPDATA%\IEC-site-change-manager\` | weld_cache、UI 偏好、app.log、崩潰報告 |

- [ ] 現況「project_dir＝exe 旁」是**可攜模式**，適合放共用碟一份大家跑；但若 exe 被裝到 `C:\Program Files`（無寫入權）就全滅。首啟偵測 exe 目錄不可寫 → 引導選/建專案資料夾，路徑記在 `%LOCALAPPDATA%` 的 pointer 檔。
- [ ] `.trash/`、`staging/`、`_annotated/` 這些會長大的目錄提供健康頁清理入口。

### 4.5 第一次啟動流程

- [ ] 首啟精靈（project_guard 的 StartupDecision 已是現成骨架）：①選/建專案資料夾 ②從 template 生成 settings.json ③填專案名稱與使用者名稱 ④指向焊口表/DWG LIST（可跳過，設定頁補）⑤跑一次健康檢查落地報告。
- [ ] 種子資料：`records/seed/material_pricebook_seed.json` 已在 spec datas——首啟時複製到專案 records/（不存在才複製）。
- [ ] 首啟不可因 H: 缺席而擋死（見 4.7）。

### 4.6 升級與設定 migration

- [ ] settings：沿用 `_merge_defaults` 但加 `meta.version` 比對與逐版遷移函式表（`MIGRATIONS = {"1.3": _to_1_4, ...}`），遷移前自動備份 `settings.json.bak.{version}`。
- [ ] 資料檔：`change_order.json` 已有 schema_version（讀取容忍已做）；升級寫入策略＝**讀舊寫新、不回頭批量改檔**（現行 from_dict 已支持）。
- [ ] exe 升級＝整包 onedir 換新（可攜模式下提供 `升級說明.txt`：關程式→蓋資料夾→資料在專案資料夾不受影響）。`check_release_package` 已擋頂層夾帶專案資料，維持。

### 4.7 H 槽 / 雲端硬碟 / 本機路徑不可用時

- [ ] 現有基礎不錯：來源健康卡會顯示「找不到/被占用」；精靈 `existing_welds` 回 source status 而非炸掉。要補的是**全域 degrade 敘事**：H: 斷線時——主 GUI 頂部黃條「焊口表離線：使用 {日期} 快取」（weld_cache 有 mtime 可顯示）、精靈允許以快取查詢＋新焊口手填、輸出中心擋 live-lookup 相關輸出並說明原因。
- [ ] `_pdf_source_health` 對大資料夾的 rglob 掃描在斷線網路碟上會 hang——所有對 H: 的存取加 timeout/背景執行緒（pywebview js_api 是同步呼叫，長 IO 會凍住 UI）。**需要實機驗證**（拔網路線實測設定頁/精靈/輸出中心三處行為）。
- [ ] 出單（export_change_order）目的地不可寫時：目前 FileExistsError/OSError 會被信封接住回前端——補「重試/改本機暫存再補交」選項為佳（P2）。

### 4.8 log 檔與錯誤回報

- [ ] P1-9 做完（統一 logging）後：exe 版把未捕捉例外掛 `sys.excepthook` → 寫 crash log + MessageBox「發生錯誤，已產生診斷包於…」→ 呼叫 `diagnostics.collect_support_bundle()`。
- [ ] 健康頁「支援診斷包」接通（後端已有），內容包含：logs 摘要、health 報告、build_info、settings（去除路徑中個資可選）。

### 4.9 防止封裝後 path/cwd/relative path 壞掉（總表）

| 風險點 | 檔案 | 狀態 |
|---|---|---|
| 入口 spec 指舊系統 | packaging/*.spec | **P0-1 必修** |
| open_wizard subprocess | co_main_bridge.py | **P0-2 必修** |
| 前端 `_HERE/co_*_web/index.html` | co_main_app/co_wizard_app | datas 對齊後可用，spike 驗證 |
| cwd fallback | co_bridge.`Path.cwd()` | 移除（4.3） |
| records_dir 以 `__file__` 上跳 | co_bridge/material_taxonomy | 改 resources.* |
| 模板 resource_path | config.py | ✅ 已正確 |
| frozen project_dir=exe 旁 | resources.py | ✅（補不可寫偵測） |
| 快取寫共用碟 | weld_control | P1-6 |
| 字型絕對路徑 `C:\Windows\Fonts` | owner_data_report._preview_font | Windows 可用；已有 fallback，可接受 |
| poppler `pdftoppm` 外部指令 | owner_data_report | exe 內無 poppler → 確保 PyMuPDF 進包（requirements 已有），poppler 視為有則更快的加速器 |

---

## 5. 資料模型與企業級資料治理

### 5.1 現況盤點與分類（哪些該 commit、哪些不該）

| 檔案 | 性質 | 現況 | 應然 |
|---|---|---|---|
| `settings.json` | **本機/專案實例設定** | git 追蹤、含 H: 絕對路徑與 last_browse_dir | ❌ 停止追蹤；repo 留 `settings.template.json`（P0-6） |
| `records/records.json` | runtime 主紀錄（舊鏈） | git 追蹤、今日被清空 [E7] | ❌ 停止追蹤；exe 時代它屬專案資料夾 |
| `records/app_settings.json` | 本機 UI 覆蓋設定 | 已 ignore ✅ | 維持；長期併回 settings.json 單一來源（雙檔優先序 `saved or settings or config` 已經在製造「為什麼改了沒生效」的坑） |
| `records/project_parts.json` | 專案 runtime 資料 | 已 ignore ✅ | 維持；加 schema_version |
| `records/billing.json` / `billing_batches.json` | 專案 runtime 資料 | 追蹤中（近乎空） | ❌ 停止追蹤；加 schema_version |
| `records/weld_snapshot.json` | 舊鏈快取 | 追蹤中 | ❌ 停止追蹤（可重建） |
| `records/material_pricebook.json` | 半模板半資料（16,887 筆生成物＋匯入品項）| git 追蹤 6.4MB | 拆解（見 5.3）：生成物不該進 git，匯入品項屬專案資料 |
| `records/material_taxonomy.json` | **標準模板/規則** | 追蹤 ✅ | 維持（這是「產品」的一部分，隨版本發佈） |
| `records/material_catalog_rules.json` | **標準模板/規則** | 未追蹤（新檔）[E1] | ✅ 加入追蹤＋datas |
| `records/sample_generation_summary.json` | 生成稽核產物 | 未追蹤 | ignore 或移 `packaging/generated/` |
| `template/*.xlsm` | 標準模板 | 追蹤 ✅ | 維持 |
| `control/wizard_data.json` | 模板（語句庫） | 追蹤 | 維持但與精靈硬編語句合一（P1-8） |
| `attachments/`、`staging/`、`output/`、`logs/`、`.trash/` | runtime | 已 ignore ✅ | 維持 |
| `.weld_cache/`（在 H:）| 快取 | 寫在共用碟 | 移本機（P1-6） |

### 5.2 主資料流的單一真相

新架構的真相鏈是對的，要白紙黑字定下來（寫進 PROJECT_MAP 重寫版）：

```
焊口管制表 Excel（外部，業主域） ←唯讀→ weld_lookup（+快取）
attachments/{單號}/change_order.json   ＝ 修改單唯一真相（schema 0.2）
records/project_parts.json             ＝ 本案材料登記真相
records/billing.json                   ＝ 請款狀態真相（byId → 單號）
canonical_report_set（記憶體）          ＝ 匯出用唯讀投影（不落地為真相）
weld_snapshot.json / records.json      ＝ 舊鏈遺產，唯讀相容，排定退役
```

規則：**任何新功能只准寫 change_order.json / project_parts / billing 三處**；匯出永遠走 canonical_report 投影，不准 renderer 自己讀雜檔。

### 5.3 material_pricebook 的雙軌收斂

現況同時存在「16,887 筆物化枚舉（v4.0）」與「規則 lazy 展開」，id 方言還不一致 [E3]。收斂方案：

1. 宣告**規則庫（material_catalog_rules.json）為總庫唯一真相**；pricebook.json 降級為「**匯入品項庫**」——只存 `import_material_excel` 併入的管制單品項與歷史 303/442 遺產（幾百筆），生成的 16,887 筆從檔案移除（要用時 lazy 展開）。
2. `co_main_bridge.pricebook()` 廢除「全量回傳」路徑（前端已優先走 summary/query，留著只是 fallback 陷阱），fallback 改回傳匯入品項庫。
3. 一次性 migration：掃 pricebook 標記 `來源 != 標準總庫` 的品項保留，其餘刪除；registered id 依 P1-4 對照表重寫。
4. 驗收：`records/material_pricebook.json` <500KB；總庫分頁/註冊/精靈選料行為不變（測試護航）。

### 5.4 schema version 需求表

| 檔 | 現況 | 動作 |
|---|---|---|
| change_order.json | `schema_version: "0.2"` ✅ | 維持；變更走加欄位＋容忍讀取 |
| report_set | `report_set.v1`/`report.v1` ✅ | 維持 |
| material_taxonomy / catalog_rules | v1 ✅ | 補 `id_scheme` 欄（P1-4） |
| project_parts.json | ❌ 無 | 加 `{"schema_version":"project_parts.v1", registered, custom, meta}` |
| billing.json / billing_batches.json | ❌ 無 | 加 v1 |
| settings.json | meta.version 有但無讀取端 | 加版本判斷＋遷移表（4.6） |
| weld_cache | 無（快取可拋） | 加 `cache_version`，不符直接重建（避免升級後讀到舊形狀） |

### 5.5 migration layer

需要，但保持輕量：`control/schema_migrations.py` 一個檔——`ensure_latest(kind, data) -> data`，內部 per-kind 版本遞移函式；所有 json_store 讀取點過這層。**不做**批量磁碟改寫工具（雲端共用下批量改檔＝同步災難），一律讀時遷移、寫時落新版。

### 5.6 audit log / operation log

- 已有三件半成品：`change_order.audit.history[]`（每單永久軌跡 ✅，缺 who → P2-6）、`operation_journal`（當機復原，僅舊 GUI 在用）、billing 的 `billing_audit`。
- 建議補一條**專案級操作流水**：`records/operations.log.jsonl`（append-only，一行一事件：when/who/action/target/summary），由 json_store 寫入層順手記——多人共用時「昨天誰改了 88 那張單」就查得到。輸出中心/匯出等大操作包 operation_journal（新鏈目前完全沒用它）。
- 業主資料包**不含**任何 audit/人名。

### 5.7 匯出資料包資料夾結構

現況：`staging/site_output_center_web/`（開發檔＋`owner_data_report/` 混居）。問題：①交付時若整包複製會夾帶 canonical_report_set.json、模板 json 等內部檔 ②放在 `staging/`（照片收件匣）語意錯位。建議：業主包輸出根改 `output/owner_package_{date}/owner_data_report/…`（或設定的 output_dir 下），開發檢查包維持 staging 或 `output/dev_check/`；「開啟業主資料包」按鈕直接開到 owner_data_report 那層（現已是）並在資料夾放一頁 `讀我.txt`（封面 sheet 的使用說明複製一份）。

---

## 6. 焊口邏輯審查

### 6.1 「內部只記 重焊/新焊，匯出時再轉案場標示」——方向裁定：**正確，維持**

理由：①案場規則彼此矛盾且無統一慣例（老一輩符號亂象是既定事實），任何把案場碼當內部主鍵的設計都會在下個案場報廢 ②現行 canonical 模型已把「事件」與「碼」分開（WeldEvent 記 origin/base/op/rework_index，code 是派生物）③匯出層已示範轉換（`_weld_change_label`→新增/修改、`_weld_change_factor`→係數）。這正是企業級做法：**內部 canonical、邊界 codec**。

### 6.2 內部 canonical weld model 應該長什麼樣（現況已達 8 成）

現有 `WeldEvent{joint_type, origin, base, op, rework_index, code, spec{size,sch,material,weld_type}, spec_source}` 基本正確。補三件：

1. **`field_action`（選填）**：現場動作「裁切/加長/縮短/拆除不重焊」。目前 Op enum 已把這些合併映射成 REWORK（`_coerce_weld_op`），語意有損——匯出說明、統計「本月裁切幾口」都需要原始動作。做法：WeldEvent 加 `field_action: Optional[str]`，UI 下拉提供，`op` 維持二值不變（codec 不受影響）。
2. **`spec_snapshot` 語意寫死**：`spec_source=looked_up` 的 spec 是「出單當下」快照。目前 owner report 匯出時**又 live 查一次管制表**（`_lookup_weld_info`）——管制表事後被人改，重出資料包數字就變，且離線時匯出降級。建議：出單時把 `lookup_info` 的完整結果（含 DB數/預算編號/I.D）存進 WeldEvent（`spec_ext: {db, budget_no, inside_diameter}`），匯出**優先用快照、查無才 live**，並在開發檢查包標註快照 vs live 差異。
3. **修一個語意混流**：`canonical_report._weld_rows_from_change_order` 把 `op`（"重焊"/"新焊"）塞進 `mark` 欄——但 mark 在舊資料語意裡是 r/a/b 尾碼。多數路徑因 `code` 存在而沒事（排序/顯示優先用 code），但 code 為空的邊緣資料會經 `_weld_code` 拼出「2重焊」這種怪碼，且下游 `_weld_change_label` 得靠列舉中文詞來救。應改為 `mark = code 尾字母`、另帶獨立 `op` 欄，讓兩種語意各走各的。

### 6.3 分層表（誰負責什麼）

| 層 | 持有 | 例 |
|---|---|---|
| 現場動作 | `field_action`（新增，選填） | 裁切/加長/縮短 |
| 事件語意 | `origin`+`op` | existing+重焊 / new+新焊 |
| 重工序 | `rework_index`（整數） | 第 2 次重工 |
| 案場碼 | `code`＝codec(origin, base, rework_index, scheme) | `2b`、`1001`、`w88a` |
| 匯出標籤 | 匯出 codec 設定 | 新增/修改、係數 1/1.5 |

`1000+` 是 `WeldScheme.new_weld_base` 的案場參數（已可注入）；`原焊口+r` 慣例屬舊資料，parse 已容忍（`is_cut: "r" in code`），新單不再產 r 碼——保持。

### 6.4 DB數 / 預算編號 / I.D / 尺寸 / 材質 / 厚度如何穩定帶出

- 讀取端已穩：`weld_lookup.lookup_info` 多同義字（DB數/DB/D.B./DI/Dia-Inch/管徑吋數；預算編號/Budget No；I.D/內徑），短欄名走精確匹配防「ID」誤撞——這段寫得很好。
- 不穩的是**時機**（見 6.2-2 快照）與**單位規整**：`_format_db_text` 會從尺寸推 DB（DN→吋對照）——推導值與表值來源要在開發包中可區分（加 `db_source: table|inferred`）。
- 驗收：出單→改管制表該列尺寸→重出業主包，焊口統計仍為出單當時值；開發檢查包 issues 列出「與管制表現值不符」清單。

### 6.5 匯出欄名與值轉換、各案差異的設定頁表達

把現在散在 `owner_data_report.py` 的轉換抽成**匯出 codec 設定**（settings 新 section，設定頁一張「焊口編碼與匯出」卡）：

```json
"weld_scheme": {
  "new_weld_base": 1000,
  "rework_letters": "abcdefghijklmnopqrstuvwxyz",
  "export_labels": {"new": "新增", "rework": "修改"},
  "export_factors": {"new": 1, "rework": 1.5},
  "weld_no_header": "銲口編號"   // 案場表頭用字（焊/銲）
}
```

設定頁呈現建議：卡片顯示「新焊口起始號 1000＋、重工字母 a/b/c、匯出標籤 新增/修改、係數 1/1.5」＋一行**即時示例**（「例：焊口 2 第二次重工 → 2b，全新焊口 → 1001」），改參數示例跟著變——工務人員不用讀文件就能核對本案規則。`WeldScheme` 已是 dataclass 可注入，接線成本低。

### 6.6 涉及檔案彙總（§6 施工面）

`change_order.py`（field_action/spec_ext）、`change_order_builder.py`（history_codes 注入＝P0-3、scheme 從 settings 建）、`weld_codec.py`（不動）、`weld_lookup.py`（lookup_info 已備）、`co_bridge.py`（build/export 帶歷史碼、出單寫快照）、`canonical_report.py`（mark/op 分流）、`owner_data_report.py`（吃 codec 設定與快照）、`gui_settings 對應的新設定卡（co_main_web）`。

---

## 7. 材料邏輯審查

### 7.1 「枚舉 → 規則生成/自建」方向裁定：**正確，且後端已到位，問題在雙軌與 id**

`material_catalog_rules.py` 的 9 種模式（single/dual_schedule、olet、rating、bolt、fastener、u_bolt、support、support_dn）已覆蓋你問的所有品類：

| 品類 | 建模 | 現況 |
|---|---|---|
| 管件（彎頭/三通/管帽…） | 規則生成：DN × SCH × 材質白名單 | ✅ |
| 大小頭/異徑三通/補心 | `dual_schedule`：DN 對（大端>小端、步距≤4 檔） | ✅ |
| Olet | `olet`：主管×分支（分支∈常用檔或≥主管半徑） | ✅ |
| 閥件/法蘭/墊片 | `rating`：DN × 磅級(150/300/600/800#) × 白名單 | ✅ |
| 螺栓 | `bolt`：M徑 × 長度（taxonomy 軸） | ✅ |
| 鋼板/型鋼/底板 | `support`：規格枚舉（L40x40x5…）× 材質 | ✅（規格檔案場可改 rules json） |
| 管支撐（管夾/管鞋） | `support_dn`：DN × 材質 | ✅ |
| 管架組合 | `support_bom` Type 展開 | ✅ |
| 特殊儀器（視鏡/阻火器/流量計…） | **適合枚舉/匯入**，不硬造規則 | 走 `import_material_excel` ✅ |

**枚舉 vs 規則的判準**（寫進開發文件）：規格空間是「軸的笛卡兒積」→ 規則；規格是「型錄逐條」→ 枚舉匯入。兩者都必須落到同一個 frontend row 形狀與同一 id 空間。

### 7.2 雙尺寸/特殊約束防亂填

後端 `build_catalog_row` 已強制：尺寸1>尺寸2、單尺寸禁尺寸2、SCH/磅級白名單、材質白名單（超出白名單會明講「請先把材質加入材料規則庫」）。前端 `regBuildCurrentSpec` 也先擋一輪。**補強兩點**：①Olet 自建走 `dual_schedule` 同一驗證，但 `_olet_pairs` 的分支合法性（常用檔/半徑規則）只在枚舉端——自建 Olet 也要過 `_olet_pairs` 等價檢查 ②錯誤訊息目前是純文字，前端把對應欄位標紅（欄位級 error 已有 `.bad` 樣式可用）。

### 7.3 「登記材料」與「紀錄管理材料明細」防撕裂

現況的撕裂點與修法＝P1-3（resolver 統一）＋P1-4（id 凍結與遷移）。再補兩個閉環：

1. **待登記 → 轉正閉環**：精靈「待登記材料」與主 GUI `matPickPending` 產生 `component_id=""、備註含「待登記」` 的列。目前沒有任何地方彙整它們。建議：材料管理頁加「待登記」徽章視圖（掃全部 change_order.json 的無 id 材料列 → 一鍵「建立到本案並回填此單」，回填走 save_record）。健康頁 integrity_audit 加一條「N 筆材料待登記」。
2. **紀錄明細改料時的規格連動**：主 GUI 明細裡選了本案配件後 size/sch/mat 變唯讀（`cellRO`）✅ 正確；但 `qty` 沒有單位換算/小數約束（米 vs 個），至少 `qtyValid` 加「單位=個/支/組時須整數」。

### 7.4 UI 自建受控的成熟度

已達標的：兩段式（選類型→軸下拉）、軸選項由 `catalog_summary.by_icon.by_part` 逐級縮小、建立即登記。建議增補：①自建成功後在列表高亮該列並捲動到位（現在只有狀態列文字）②「複製本案料號」很貼心，補「匯出本案配件 Excel」按鈕直達（已有，在匯入匯出選單內——移出來一層）③custom 材料（管架展開）目前無法從 UI 刪除/編輯——本案配件視圖對 `project_only` 列提供「移除自本案」。

---

## 8. Excel / 業主資料包審查

整體評價：**索引 xlsx 的骨架已是可交付水準**（品牌表頭/斑馬紋/freeze/autofilter/fitToPage landscape/相對連結/縮圖卡），以下按你列的檢點逐項給結論與升級建議。

### 8.1 逐項檢核

| 檢點 | 現況 | 判定與建議 |
|---|---|---|
| 資料索引 | 15 欄：項次/單號/日期/ISO流編/圖號/Line No./說明/焊口詳細/材料摘要/前/後/圖說縮圖/3 個「開啟」連結 | 結構好。**排序**目前依 (date_str, folder) 字典序——改為 日期 desc → 流水號自然序 → 單號（工務找單習慣新在上）。「項次」隨排序重編。 |
| 焊口統計 | 每口一列：單號/日期/ISO流編/焊口編號/尺寸/材質/厚度/新增或修改/係數/DB/預算編號 | 欄序建議把 DB、預算編號 移到 尺寸 旁（計量核對動線）；焊口編號排序沿 `_owner_weld_sort_key` ✅（數字→r→a/b/c）。加**總計列**（口數、Σ係數、依尺寸小計）——業主第一個問的就是總數。 |
| 用料統計 | 每列一料 | 加「彙總」第二區或第二張表（component+size+sch+mat+unit 聚合 Σqty——aggregates.material_qty_by_key 現成）；`qty` 寫入時保持數值型別（目前 `_number_or_text` 已處理，勿變字串）。 |
| before/after/PDF 縮圖 | 260×180 標題卡、EXIF 轉正、置中貼圖、PDF 首頁渲染雙 fallback | 好。**直立照片**：thumbnail contain 後左右留白屬正常；若要更好看，偵測 h>w 時卡內圖區改直式（縮圖卡是自繪的，改 `_save_preview_card` 佈局即可）。 |
| 儲存格排版 | 列高 145pt vs 圖高 180px≈135pt | 圖片底部貼近下一列邊界，Excel 版本不同可能壓線——列高調 150pt 或圖高 170px 留 buffer。**需要實機驗證**（Windows Excel 開啟目測）。 |
| 圖片置中 | openpyxl anchor 固定左上角 | 卡片寬 260px vs 欄寬 40 字元≈285px，右側留 25px——若要精確置中，欄寬四捨五入為 (260px+2×offset)/7px 或改用 AnchorMarker 帶 colOff（EMU）微調。屬 polish 級。 |
| 超連結搬移 | `_relpath` + `/` 分隔 ✅、`_link_cell` 統一 | 設計正確。**兩個必驗場景（需要實機驗證）**：①資料夾連結（第 2/13/14/15 欄連到「資料夾」而非檔案）在 Excel 點擊行為＝開檔案總管，部分安全設定會擋 ②整包移到 Google Drive 網頁版/別台機器對應碟號後開啟。建議每次匯出附 `連結說明.txt`（連結為相對路徑，請整個 owner_data_report 資料夾一起搬）＋把「開啟」改成連到**第一張照片檔**而非資料夾（檔案連結相容性 > 資料夾連結）作為選項。 |
| PDF→PNG | poppler(144dpi) → PyMuPDF(2x) → 占位卡 | 打包後以 PyMuPDF 為主（4.9 表）；渲染失敗的占位卡含檔名 ✅。多頁 PDF 只取首頁——索引卡夠用；圖說多頁時在卡片標「共 N 頁」（`_pdf_pages` 已會數頁，canonical 有存）。 |
| 業主 vs 開發分流 | report_type: owner-data / developer / both ✅ | 維持；補 §5.7 的資料夾分離，並確保 owner 包內**零**開發檔與零內部欄位（fingerprint/status/completeness 不得出現在業主 sheet——現況正確，守住）。 |
| 文字換行 | `_summary_to_cell_lines` 把「、」拆行 + wrap_text ✅ | 說明欄（G 欄 36 字寬）長文會撐高列——列高固定 145，超長被截視覺。建議說明>200 字時截斷加「…全文見單內 note」。 |
| 欄位命名 | 「ISO流編」「工務修改確認單編號」 | 與 UI 的「流水號」「報告編號」不同名。**定一張詞彙表**（內部詞 ↔ 業主詞）放 docs，匯出層統一從詞彙表取——換案場業主要求改叫「圖號序號」時只改一處。 |
| 封面/照片明細 | `_write_cover_sheet`、`_write_photo_detail_sheet` 已寫好但**未被呼叫**（export 只出 3 表） | 接上封面（放專案名/產出時間/統計/使用說明——內容函式都寫好了）；照片明細視業主需求開關。 |

### 8.2 報表等級優化（超出檢點的建議）

1. **單號人類可讀化已做**（`CO-{series}-{date}-{NN}`）——但轉換規則散在 `_clean_report_label` 正則裡，納入 §6.5 的匯出 codec 設定（有的業主要 `PCN-` 前綴）。
2. 索引表加**狀態欄過濾預設**：completeness incomplete 的單在開發包顯示、業主包預設剔除或標色——現在 include_report_keys 由勾選決定，建議業主包產出前彈「N 筆未完整（缺 after 照…），仍要包含？」（canonical issues 現成）。
3. 焊口統計表的係數欄目前對「非新增非修改」回空字串——保持空但在開發包 issues 記一筆，避免 Σ係數靜默少算。

---

## 9. UI/UX 審查（非工程使用者視角）

### 9.1 「還像皮」的按鈕/區塊（按了沒有真效果）——展示前全數處理

| 位置 | 元件 | 現況 | 處置 |
|---|---|---|---|
| 請款追蹤 | 「匯出報表」「請款單」 | **無 onclick** | P1-10：接真功能或移除 |
| 請款追蹤 | 建立批次/更新批次狀態 | toast「尚未接入」＋假 BATCHES（台積電 F18） | P0-5/P1-10 |
| 健康 | 「修復」 | toast 未接入（後端 auto-repair 存在） | 接通 |
| 健康 | 診斷包 ▾ 兩項 | menuPick 佔位 | 接 collect_support_bundle |
| 健康 | 初始 HTML 假 issues/假統計 | 後端蓋掉前是假的 | 改 loading 骨架 |
| 材料 | 「儲存」（savePricebookNote） | toast「尚未開放」 | 移除（登記/匯入本來就即存） |
| 產出報告 | 「停止」 | 後端不可中止，按了只解釋 | 改 disabled＋tooltip，或做成可中止（P2） |
| 產出報告 | 進度條 | 時間驅動假進度（18%+4%/s） | 後端回報階段（收斂 canonical → 複製資產 → 產 xlsx → 縮圖），橋加 progress 查詢或分段回呼 |
| 設定 | 進階產出選項 4 個開關 | **未綁 settings**（純 UI 狀態） | 綁 runtime 設定或先藏 |
| 紀錄管理 | 起迄日期兩個輸入框 | 無過濾邏輯（紀錄/請款兩處） | 接進 renderRecords/renderBilling 或移除 |

### 9.2 使用者會「不知道下一步」的斷點

1. **精靈出單成功後**：只有 toast＋狀態列一行字。應出成功面板：單號大字＋「開啟資料夾／回主畫面看紀錄／再開一張」三顆按鈕（開資料夾後端 `_open_path` 現成，橋補一個方法）。
2. **主 GUI 首次開啟、精靈還沒出過單**：產出報告左欄空狀態文案已不錯（「修改單精靈存成草稿後…」），但**沒有一顆直接開精靈的按鈕**——空狀態加「開啟修改單精靈」主按鈕。
3. **勾選→產出的關聯**：紀錄管理勾選框在最左、輸出中心按鈕在右下角落——第一次用看不出因果。勾了 N 筆時讓「輸出中心」按鈕變主色並帶數字「輸出中心（3）▾」。
4. **設定來源三張卡**：狀態 pill「需檢查/被占用」很好，但**下一步動作**要長在訊息旁——「被占用」旁給「重試」、「缺欄位」旁給「欄位」按鈕高亮。
5. **精靈焊口頁在管制表未設定時**：source-empty 訊息有了，但使用者被卡死在這頁——訊息內給「去主程式設定焊口表」說明（精靈是獨立進程，至少講清楚去哪裡設）。

### 9.3 需要進度/執行中狀態的地方

輸出中心（9.1 假進度）、匯入材料 Excel（16,887 筆 merge 會卡幾秒，按鈕要 busy）、`existing_welds` 首次載入大表（快取未建時 Excel 全讀，精靈「載入焊口」按鈕加 spinner——pywebview 同步橋會凍 UI，長操作要移背景執行緒＋輪詢，這是 pywebview 架構上要提早決定的事，列 P2）、健康「重新檢查」（integrity_audit 掃全樹）。

### 9.4 空/錯/成功狀態盤點

- 已有且質感好：紀錄/材料/請款空狀態插畫、查無搜尋結果插畫、精靈焊口空狀態線稿、來源健康三色 pill。
- 缺：**全域「後端未連線」狀態**（P0-5）；燈箱圖載入失敗只有 toast（圖區應顯示破圖佔位）；輸出中心失敗只在日誌（狀態列已有 err 樣式 ✅ 保持）；精靈 staging 空時「去哪裡放照片」沒講（提示 staging 資料夾路徑＋「開啟資料夾」）。

### 9.5 需要「?」說明的設定

設定頁 help-tip 系統已存在且文案不錯（專案名/DWG/焊口表/圖面資料夾/輸出位置都有）。要補：「用途對照」表加一條**係數與焊口編碼**（§6.5 新卡）；進階選項每個開關的後果（「略過未變更＝依內容指紋…」）；健康頁解釋「修復會做什麼、不會動什麼」（現有 health-hint 一句話，展開成 tip）。

### 9.6 Excel 欄位映射預覽

**已實作**（§1.7），評價：這是全設定頁最企業級的一塊。優化三點：①預覽 modal 的「欄位」按鈕目前是來源卡上的次要 ghost 按鈕——當健康狀態=缺欄位時把它升級成主色並帶紅點 ②預覽表格勾選欄位後**沒有即時重驗**——勾完即呼 `save_source_schema`→`app_settings` 刷健康，讓使用者當場看到綠燈 ③大檔預覽 `load_workbook` 同步讀（凍 UI 風險同 9.3）。

---

## 10. 測試與驗收策略

### 10.1 測試矩陣

| 層 | 範圍 | 現況 | 要補 |
|---|---|---|---|
| 單元 | 引擎五件組、codec 邊界（2 vs 20、字母溢位）、材料規則驗證、billing 狀態機、parsers/utils | ✅ 447 綠 [E2] | P0-3 跨單派號、P1-1 表頭列寫入、json_store 原子性、schema_migrations |
| 橋整合 | test_co_bridge / test_co_main_bridge（信封、防呆、檔案落地） | ✅ 且未 commit 新增 252 行 | 材料 resolver 統一後的一致性測試（兩橋同 id 同形）、save_record 刪列對齊、未連線/壞 JSON 容錯 |
| 真實 Excel 樣本 | `docs/參考/` 4 張管制單、`docs/00.../焊口管制表-115.06.12.xlsx` | 匯入器有測試；焊口表 fixture 為合成 | 用脫敏真表建 `tests/fixtures/`：表頭第 3 列、銲字表頭、混雜安裝列（屬性.1）、DB/預算欄——lookup_info 全鏈驗證 |
| 圖片/PDF 標註 | pdf_overlay renderer 有測 | 標註儲存（save_annotated/save_pdf_annotation/save_photo_annotation）有部分 | 補：標註 PNG 尺寸=原圖、PDF 標註不動其他頁、`_annotated` 檔名遞增 |
| 匯出資料包 | test_owner_data_report（+137 行新增）、site 輸出鏈 | ✅ | 補：**相對連結驗證**（openpyxl 重開 xlsx 斷言 hyperlink 全為相對且目標存在）、搬資料夾後目標仍在（temp 兩層搬移測試）、業主包不含內部檔清單 |
| 封裝後 smoke | run_packaged_cli_smoke / run_release_smoke / check_release_package | ✅ 架構在，但對象是舊 exe | 對新 exe 重寫：`exe --health-check`、`exe --wizard --smoke`（開窗 3 秒自關或 headless 檢查 import）、check_release_package 資產清單更新 |
| 異常情境 | — | 零散 | 見 10.2 專表 |
| 並發 | — | 無 | P1-2 鎖的搶鎖/心跳/殭屍測試 |
| 前端 | — | 無 | 最低限：Node 不引入的前提下，把純函式（weld 排序、狀態判定）搬 bridge 端測；UI 走查改人工 checklist（10.4） |

### 10.2 異常測試最少清單（每項一個 pytest case）

1. 焊口表路徑指向不存在磁碟（H: 拔線模擬：路徑不存在）→ `existing_welds` 回 source.ok=false 且訊息可讀，精靈不炸。
2. 焊口表被 Excel 開啟（Windows 實測 PermissionError；沙箱以 monkeypatch 模擬）→ 健康卡「被占用」、回寫路徑回明確錯。**需要實機驗證**（真鎖行為僅 Windows 有）。
3. 欄位改名（焊→銲、加空白換行）→ resolve 成功；改到不存在 → 健康卡列缺欄。
4. sheet 改名/多 sheet 帶 OLD-NEW → 自動選對並在訊息標「自動辨識」。
5. 圖面 PDF 不存在/資料夾空 → auto_drawing_pdf 回 not_found，前端顯示原因文字。
6. change_order.json 壞 JSON/半截檔 → records() 略過該筆並在健康頁報一筆（目前是靜默略過——補 issue）。
7. 匯出時來源照片已被刪 → owner package 缺圖顯示「無檔案」卡、missing 清單有記錄（export_change_order 已有 missing ✅ 補 owner 端斷言）。
8. settings.json 損毀 → 退預設＋備份壞檔（現況退預設 ✅，補 `.corrupt.bak` 保留現場）。
9. 出單目標資料夾已存在（重複單號）→ FileExistsError 信封→前端可讀訊息。
10. 材料規則檔 schema_version 不符 → 回 DEFAULT_RULES 並健康頁提示（現況靜默退預設）。

### 10.3 最少必跑指令（寫進 `docs/測試指引.md` 與 pre-push hook）

```bash
# 1) 核心引擎 + 兩座橋（每次改動必跑，<10s）
python -m pytest -q tests/test_change_order.py tests/test_change_order_builder.py \
  tests/test_change_order_store.py tests/test_weld_codec.py tests/test_weld_lookup.py \
  tests/test_co_bridge.py tests/test_co_main_bridge.py

# 2) 匯出鏈（改 renderer/report 時）
python -m pytest -q tests/test_canonical_report.py tests/test_owner_data_report.py \
  tests/test_site_statistics_exporter.py tests/test_run_site_output_center_tool.py

# 3) 全套（commit 前）
python -m pytest -q

# 4) 打包 + 驗包 + smoke（release 前，Windows）
python tools/build_release.py            # build_info + pyinstaller + 驗包 + smoke
dist/IEC-site-change-manager/IEC-site-change-manager.exe --health-check
python tools/build_release.py --archive  # zip + sha256
```

### 10.4 人工驗收 checklist（exe 冒煙，10 分鐘版）

乾淨機器：解壓 → 雙擊 → 主 GUI 開窗（無 console 錯誤）→ 設定頁指向測試焊口表 → 健康頁全綠或可解釋 → 開精靈 → 載入焊口 → 建一張含 1 重焊 1 新焊的單（照片從 staging）→ 主 GUI 紀錄頁看到 → 編輯材料存檔 → 勾選 → 產業主資料包 → 開啟資料夾 → xlsx 縮圖/連結可點 → 整包複製到桌面再開連結仍通。

---

## 11. 建議施工順序（16 步路線圖)

### 立刻做（本週，不碰打包也該做）

| # | 任務 | 目的 | 主要檔案 | 風險 | 驗收 |
|---|---|---|---|---|---|
| 1 | 工作區收斂 commit（拆 3–5 個語意 commit）＋修 `test_material_catalog_generator` | 建立可回溯基準線 [E1][E2] | 全工作區 | 拆錯歸屬——用 `git add -p` | `git status` 乾淨、全套 pytest 收集無錯 |
| 2 | **焊口跨單派號修復**（P0-3 第 1 層：歷史 change_order 併入 existing_ids） | 堵領域級重號 | change_order_builder / co_bridge / tests | 掃描效能（同 series 通常 <10 單，可忽略） | §P0-3 驗收測試綠 |
| 3 | json_store 原子寫收斂（P0-4 第 1 層） | 資料不半截 | 新 json_store.py、co_main_bridge | 大檔 pricebook 改寫路徑順手降級（§5.3 之前先照舊） | grep 零裸 write_text、kill 測試 |
| 4 | 前端假資料下架＋未連線狀態（P0-5） | 展示安全 | co_main_web/index.html | 低 | 瀏覽器直開全空狀態、無台積電字樣 |
| 5 | settings 模板/實例分離＋records.json 出 git（P0-6） | 部署撕裂止血 | settings.template.json、.gitignore、settings_manager、project_guard | 既有機器的 settings 保留（ignore 不刪檔） | clone 首啟自動生成、git 乾淨 |

### 封裝 exe 前做

| # | 任務 | 目的 | 主要檔案 | 風險 | 驗收 |
|---|---|---|---|---|---|
| 6 | **pywebview 打包 spike**（半天）：最小視窗+js_api+onedir 丟公司機 | 技術面最大不確定性先落地 | packaging/spike/ | pythonnet frozen 問題——提早知道提早繞 | 乾淨機開窗、api 呼叫成功（**需要實機驗證**） |
| 7 | 新 spec + 入口分流（P0-1、P0-2）：datas/hiddenimports、`--wizard` argv | exe 打的是新系統 | spec、co_main_app、co_main_bridge、build_release DEFAULT_SPEC | spike 學到的坑全在這步消化 | §P0-1/P0-2 驗收 |
| 8 | check_release_package 資產清單與 smoke 對新 exe 改版 | release gate 續命 | tools/check_release_package.py、run_release_smoke.py、相關測試 | 中 | `build_release.py` 全綠 |
| 9 | 統一 logging＋excepthook＋WebView2 缺失 MessageBox（P1-9、4.8） | exe 出錯有屍體可驗 | log_config、兩 launcher、兩橋 | 低 | logs/ 有橋紀錄、故意拋錯有 crash log |
| 10 | 首啟流程與可寫性偵測（4.4/4.5） | Program Files/唯讀情境不死 | project_guard、co_main_app | 中 | 唯讀目錄啟動→引導選專案資料夾 |
| 11 | UI 死按鈕清理＋精靈成功面板＋輸出進度真實化最小版（9.1/9.2） | 給長官展示的門面 | co_main_web、co_wizard_web、co_main_bridge | 低 | 10.4 人工 checklist 通過 |

### 封裝後第一版優化（內部試用期）

| # | 任務 | 目的 | 主要檔案 | 風險 | 驗收 |
|---|---|---|---|---|---|
| 12 | 材料 resolver 統一＋id 遷移（P1-3、P1-4） | 精靈/主 GUI 同一份料 | material_resolver.py、兩橋、migration 腳本 | id 對照表要人工核 [E3] 18 筆 | 兩橋一致性測試、20/20 可解析 |
| 13 | 單寫者鎖＋占用 UI（P1-2） | 多人共用安全 | project_lock.py、launcher、頂欄 | Google Drive 同步延遲（實測調心跳參數） | 兩機併發測試（**需要實機驗證**） |
| 14 | 管制表回寫復活（P0-3 第 2 層＋P1-1 表頭修正，auto_sync 設定生效） | 管制表不再靠手抄 | weld_control、co_bridge、設定頁 | 寫別人的 Excel——失敗不擋出單、全程 journal | 表頭第 3 列 fixture 回寫正確、拔線不擋出單 |
| 15 | 焊口匯出 codec 設定卡＋spec 快照（§6.2/§6.5） | 換案場不改碼 | change_order、co_bridge、owner_data_report、settings、設定頁 | 舊單無快照→匯出 fallback live 查（相容） | 改係數報表跟動、離線重出數字不變 |

### 企業版長期演進

| # | 任務 | 目的 | 驗收 |
|---|---|---|---|
| 16 | 服務層抽離（P2-1）→ pricebook 雙軌收斂（§5.3）→ 操作流水/使用者名（§5.6、P2-6）→ 效能索引（P2-3）→ FastAPI+DB spike（P3-1） | 中央化鋪路 | 各自條目驗收；DB spike 以 change_order schema 直落 SQLite 讀寫同測試綠 |

---

## 12. 給施工 AI 的明確任務切片

每片＝一個獨立 commit，附建議 commit message。**共同紀律**：動工前先 `git diff --stat` 報範圍；只准碰列出的檔案；每片附測試；不動引擎五件組除非切片明說。

1. `test(material): rewrite catalog generator test against rule-based tool` — 對準 `tools/generate_material_catalog.py` 新介面（write_rules/--expanded），刪 build_catalog 舊斷言。檔案：`tests/test_material_catalog_generator.py`。
2. `feat(weld): include same-series change-order history in code allocation` — builder 加 `history_codes` 參數；co_bridge 掃 `{series}_*/change_order.json` 餵入。檔案：`control/change_order_builder.py`、`control/co_bridge.py`、`tests/test_change_order_builder.py`、`tests/test_co_bridge.py`。測試：export 2a/1001 後第二張得 2b/1002。
3. `refactor(store): centralize atomic json io in json_store` — 新 `control/json_store.py`；替換 co_main_bridge 8 處裸 write_text 與三份 `_read_json`。檔案：上述＋`tests/test_json_store.py`。
4. `fix(ui): remove demo data and add disconnected state to main gui` — 空陣列化 records/BILL/BATCHES/PRICE、健康 tab 假列改 loading、未連線紅條、刪 money()/台積電。檔案：`control/co_main_web/index.html`。
5. `chore(settings): split template vs instance settings` — `settings.template.json`、.gitignore、settings_manager 首啟複製、`git rm --cached settings.json records/records.json records/weld_snapshot.json records/billing*.json`。
6. `chore(package): add webview packaging spike` — `packaging/spike/`（最小視窗+說明），結論寫進 `packaging/README.md`。（此片允許失敗回報，不合入主 spec）
7. `feat(package): pyinstaller profile for pywebview main gui` — 新 spec（datas/hiddenimports 如 §4.3）、build_release `--spec` 預設切換、check_release_package 資產清單。檔案：`packaging/IEC-site-change-manager-web.spec`、`tools/build_release.py`、`tools/check_release_package.py`、`tests/test_packaging_spec.py`。
8. `fix(wizard-launch): frozen-safe wizard spawn via --wizard argv` — co_main_app argv 分流、open_wizard frozen 判斷。檔案：`control/co_main_app.py`、`control/co_main_bridge.py`、`tests/test_co_main_bridge.py`（monkeypatch frozen）。
9. `feat(logging): route bridges and launchers through log_config` — print→logger、excepthook、WebView2 失敗 MessageBox（`ctypes.windll.user32.MessageBoxW`，非 Windows 降級 print）。檔案：兩 launcher、兩橋、`control/weld_control.py`、`control/log_config.py`。
10. `fix(weld-control): honor detected header row when writing back` — add_weld/add_welds_batch 用 `_resolve_sheet_and_header`；add_weld 補 resolve_col。檔案：`control/weld_control.py`、`tests/`（表頭第 3 列 fixture）。
11. `feat(material): shared resolver for registered parts across bridges` — `control/material_resolver.py`＋兩橋接入；[E3] fixture 一致性測試。
12. `feat(material): stable id scheme with unresolved surfacing and migration` — rules json 加 id_scheme、project_parts 停止自動刪 dropped 改回 unresolved、`tools/migrate_material_ids.py`。
13. `fix(records): key-based weld merge in save_record` — code/_orig_index 對齊；刪列測試。檔案：`control/co_main_bridge.py`、`control/co_main_web/index.html`、`tests/test_co_main_bridge.py`。
14. `fix(health): surface auditor failures instead of swallowing` — P1-7。檔案：`control/co_main_bridge.py`、`tests/test_co_main_bridge.py`。
15. `chore(cleanup): remove previous-project residues and hardcoded factors` — HP6 fallback、可寧衛 glob、係數進 settings（`weld_billing` 或併 §6.5 `weld_scheme`）。檔案：`control/owner_data_report.py`、`control/settings_manager.py`、`tests/test_owner_data_report.py`。
16. `feat(settings): weld export codec card with live example` — §6.5 設定 section＋設定頁卡片＋owner report 接線。檔案：`control/settings_manager.py`、`control/co_main_bridge.py`、`control/co_main_web/index.html`、`control/owner_data_report.py`、tests。
17. `feat(export): snapshot control-table specs into change orders` — WeldEvent.spec_ext、出單寫入、匯出優先快照。檔案：`control/change_order.py`、`control/change_order_builder.py`、`control/co_bridge.py`、`control/owner_data_report.py`、tests。
18. `feat(export): owner package polish (cover sheet, totals, sort, folder split)` — 接 `_write_cover_sheet`、焊口統計總計列、索引排序 日期↓/series 自然序、業主包輸出根移 output/（§5.7）。檔案：`control/owner_data_report.py`、`control/site_output_runner.py`、`control/co_main_bridge.py`、tests。
19. `feat(export): relative hyperlink integrity test` — 重開 xlsx 驗所有 hyperlink 相對且目標存在＋兩層搬移測試。檔案：`tests/test_owner_data_report.py`。
20. `feat(ui): wizard success panel and empty-state wizard CTA` — 出單成功面板（開資料夾/回主畫面）、主 GUI 空狀態開精靈按鈕、勾選數字進輸出中心按鈕。檔案：`control/co_wizard_web/index.html`、`control/co_bridge.py`（open_folder 方法）、`control/co_main_web/index.html`。
21. `feat(lock): single-writer project lock with heartbeat` — P1-2。檔案：`control/project_lock.py`、兩 launcher、`control/co_main_web/index.html`、tests。
22. `feat(weld): optional write-back of new welds to control table` — 路線圖 #14（依賴切片 2/10/21）。檔案：`control/co_bridge.py`、`control/weld_control.py`、設定頁、tests。
23. `perf(cache): move weld cache to local appdata` — P1-6。檔案：`control/weld_control.py`、tests。
24. `refactor(bridge): extract services from MainBridge`（可再拆 4 小片：records/materials/settings/output）— P2-1，信封簽名不變。

依賴關係提示：7 依賴 6；8 依賴 7；22 依賴 2、10、21；12 依賴 11；18/19 可平行；其餘大多獨立。

---

## 13. 最終結論

**① 現在可以封裝成 exe 給內部試用嗎？—— 還不行，但距離很近（約 2 週施工量）。**
阻擋的不是成熟度而是四顆硬釘子：打包 spec 打的是舊系統 [E4]、精靈在 frozen 下開不起來 [E5]、焊口跨單重號 [E6]、寫入非原子＋共用資料夾無鎖。前兩顆是「exe 能不能動」，後兩顆是「動了敢不敢用」。**Python 原始碼版其實今天就可以給 1–2 位信得過的同事試用**（單人單機、避開多人同開），先累積真實回饋，與打包工作並行。

**② 哪些問題會阻止給長官展示？**
P0-5 假資料（被點到請款批次看到「台積電 F18」直接社death）、9.1 死按鈕清單（匯出報表/請款單/修復/診斷包）、假進度條、精靈出單後「然後呢」的斷點。這些全是 1–3 天級的門面工程（切片 4、11、20），建議搶在任何展示前完成。展示腳本建議走最強的一條線：精靈源頭挑焊口 → 自動派 2b/1001 → 標註 → 出單 → 主 GUI 秒現 → 一鍵業主資料包 → 打開 xlsx 縮圖與相對連結——這條線是真的，而且很能打。

**③ 哪些問題會阻止正式導入（多人日常使用）？**
依殺傷力排序：焊口跨單重號（P0-3，領域信任毀滅級）、無鎖多人覆蓋＋非原子寫（P0-4/P1-2，資料毀損級）、材料撕裂與 id 漂移（P1-3/P1-4，實測已發生 [E3]，會讓現場放棄雙層模型回去手填）、管制表回寫缺席（新流程對管制表是「只讀不還」，計量端遲早抱怨）、H: 斷線的 degrade 未成體系（§4.7）。這五件收掉，才談得上「公司級修改單資料管理系統」。

**④ 如果只能做三件事：**
1. **焊口派號含歷史單**（切片 2）——半天到一天的工，堵掉全案唯一會直接毀掉業主信任的領域 bug。所有輸出的正確性都壓在焊口碼上。
2. **打包 profile 對準新 GUI ＋ 精靈 frozen 啟動修正**（切片 6→7→8）——沒有這件，一切「exe 化」都是空談；spike 先行把 pywebview/pythonnet 的不確定性提早消化。
3. **json_store 原子寫收斂**（切片 3）——最便宜的資料保命符，也是後續鎖機制的地基；在雲端共用資料夾這個既定部署下，這是「哪天必然發生」的事故預防。

最後一句架構師的話：這個 repo 最值錢的資產是**引擎與橋的分層紀律**（canonical model、無狀態重放、信封）——它讓「桌面工具 → 公司系統」的路是平的。接下來所有施工都應該守住同一條線：**邏輯進 services 與引擎、狀態進 schema 化的 JSON（未來的 DB 表）、UI 永遠是可丟的皮**。

---

### 附錄 A：「需要實機驗證」彙總

| # | 項目 | 驗法 |
|---|---|---|
| 1 | Windows 全套 pytest 基準（歷史 15 紅是否為 PyMuPDF/poppler 相依） | `.venv\Scripts\python -m pytest -q`，比對 [E2] |
| 2 | pywebview+PyInstaller onedir 在無開發工具公司機開窗 | 切片 6 spike |
| 3 | WebView2 Runtime 在公司機隊的覆蓋率 | IT 盤點或 spike 附檢測 |
| 4 | 業主包 xlsx 相對超連結：資料夾連結點擊行為、搬移後、Google Drive 網頁版 | §8.1 兩場景 |
| 5 | 縮圖 260×180 vs 列高 145pt 在 Excel 實際視覺 | 開啟目測 |
| 6 | H: 拔線時 設定頁/精靈/輸出中心 的凍結與訊息 | §4.7 |
| 7 | 兩台機器同開（鎖上線前後各測一次） | §P1-2 |
| 8 | Excel 開著管制表時的回寫/健康卡行為 | §10.2-2 |

### 附錄 B：本次審查讀過的關鍵檔案

`co_main_app/co_wizard_app/co_main_bridge/co_bridge/change_order(+builder/store)/weld_codec/weld_lookup/weld_control/canonical_report/owner_data_report/site_output_center(+runner)/material_taxonomy/material_catalog_rules/settings_manager/resources/config/main(入口部分)/co_main_web/index.html(全)/co_wizard_web/index.html(全)/packaging spec+README+自動Build.bat/tools(build_release、generate_material_catalog、check_* 結構)/records 全部 JSON/tests(結構+實跑)/PROJECT_MAP/DATA_FLOW_AUDIT/README/docs 目錄結構`。
