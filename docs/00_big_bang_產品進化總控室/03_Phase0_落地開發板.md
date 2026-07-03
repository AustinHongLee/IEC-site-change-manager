# Phase 0 落地開發板

目標：把現有工具從「單人可用」提升到「公司多人使用前不會先炸資料」。

## 做事順序

1. 啟動守門與專案資料夾判斷
2. 單寫者鎖與唯讀模式
3. JSON 寫入、備份與交易化
4. 一致性稽核內建化
5. 本機絕對路徑與設定可攜性
6. 最小 UI 提示與錯誤人話化

## 任務清單

| 狀態 | 任務 | 驗收標準 |
|---|---|---|
| 已做 | 建立 `project_guard` 啟動守門模組 | 可判斷第一次開檔、正常專案、缺資料夾、跑錯資料夾、JSON 損壞 |
| 已做 | 必要資料夾自動修復 | 缺 `logs/ output/ pdf/ staging/` 等空資料夾時可安全重建 |
| 已做 | `settings.json` 缺失修復 | 可用預設值重建，但標記需要使用者重新設定路徑 |
| 已做 | `records.json` / `billing.json` schema 檢查 | 壞 JSON 不自動覆蓋，停在健康檢查狀態 |
| 已做 | 單寫者 lock + heartbeat | 第二個程式啟動時不可寫入，只能唯讀或提示接管 |
| 已做 | 過期 lock 接管規則 | 程式崩潰後留下舊 lock 時，可安全判斷與接管 |
| 已做 | billing 納入自動備份 | 儲存請款資料前建立 `records/backups/` 備份 |
| 已做 | 附屬 JSON 原子寫入 | `settings.json`、`dwg_map.json`、`weld_snapshot.json` 已改為原子寫入 |
| 部分 | 多檔操作 journal | 已套用到焊口同步、資料夾 rename、records 儲存、歸檔/還原；仍需逐步盤點其他檔案搬移點 |
| 已做 | `.trash` 隔離區 | staging 清空、單檔移除、wizard 消耗 staging 原檔已先移入隔離區 |
| 已做 | `tools/audit_data.py` 模組化 | 程式內可呼叫 `audit_integrity()`，回傳結構化結果 |
| 已做 | `weld_snapshot.json` 路徑相對化 | 不寫死 `C:\Users\...`，換機不失效 |
| 已做 | 健康檢查 UI 最小版 | 能列出問題、可修復項、不可自動修復項 |
| 部分 | 防連點 / 冪等處理盤點 | 主產出、重試、紀錄儲存、請款儲存、請款匯出、歸檔/還原、編輯儲存已加防重入；仍需逐步盤點所有工具對話框 |
| 已做 | Opus Checkpoint A P0 回補 | 材料 upsert 主鍵納入 `SCH`；已請款狀態的材料列整列鎖定，重跑不可新增/更新 |
| 已做 | Opus Checkpoint A 請款總額回補 | 請款總金額改為 `焊口金額 + 材料金額` 衍生欄位，不再允許獨立手填；舊 `total` 差異會警示並於存檔清除 |
| 已做 | Opus Checkpoint A 請款稽核回補 | 請款面板儲存時產生 `records/billing_audit.jsonl` append-only old→new 事件，記錄狀態、日期、金額與備註變更 |
| 已做 | Opus Checkpoint A 請款狀態機回補 | 請款狀態改由 `billing_status.py` enum 集中管理；非法狀態/跳狀態會被擋下，金額或狀態變更需二次確認 |
| 已做 | Opus Checkpoint A 請款批次資料層回補 | 新增 `billing_batches.json` 與 `billing_batch.py`，可建立批次、驗證狀態轉換，並阻擋同一修改單同時存在於兩個活躍批次 |
| 已做 | Opus Checkpoint A 請款批次最小 UI | 請款追蹤面板支援多選修改單建立批次，建立前會阻擋活躍批次重複、已結案/作廢單與未儲存變更 |
| 已做 | Opus Checkpoint A 請款批次狀態管理 | 請款追蹤面板可檢視批次清單並更新批次狀態；狀態更新只寫 `billing_batches.json`，不隱性改單張請款狀態 |
| 已做 | Opus Checkpoint A 請款金額政策回補 | 請款層採 TWD 整數四捨五入、5% 外加稅；面板與 Excel 匯出顯示未稅小計、稅額、含稅總額 |
| 已做 | Opus Checkpoint A 材料未配價明示回補 | 價目表找不到材料單價時標記 `missing_pricebook`，UI 顯示「未配價」且不再靜默 0 元或覆蓋歷史價格 |
| 已做 | Opus Checkpoint A 價目追溯欄位回補 | 價目表 schema 補 `來源`、`生效日`、`history`；材料帶價會拍照 `價目來源` 與 `價目生效日` |
| 已做 | Opus Checkpoint A 材料類別 schema 回補 | 價目表與材料明細新增 `類別`，先支援材料/耗材/工資/雜項，供後續請款批次分線 |
| 已做 | DeepSeek 材料常數骨架接入 | 新增 `material_constants.py` 統一受控詞彙、材質 alias 與預設單位；`material_pricebook_seed.json` 通過驗證閘門 0 warning / 0 error，並可用 CLI 或價目表 UI 的 dry-run 匯入流程安全併入；空白單價列會顯示為「未定價」 |
| 已做 | 材料補價後安全重配 | 材料價目表可篩選未定價並套用補價；只更新未定價/未配價材料，手動價與已請款鎖定修改單不覆蓋 |
| 已做 | Opus Checkpoint B P0 回補 | 依 `08_Opus校準結果_CheckpointB.md` 補材料重配逐列 audit、受影響修改單清單、`需重產` 旗標、紀錄/請款跨面板未定價可見性與請款批次阻擋 |
| 已做 | 材料補價 UX 小步 | 價目表支援零件/材質下拉篩選、多選、選取目前顯示列、批次填同一單價/來源/生效日；仍需按儲存與套用補價，避免隱性寫入 |
| 已做 | 合約價格表匯入 | 新增 Excel/CSV 匯入核心、CLI 與價目表 UI 入口；先 dry-run 驗證，僅新增新 key 或補空白單價，既有有價衝突只提示並略過 |
| 已做 | 補價表模板匯出 | 新增 CSV/XLSX 匯出核心、CLI 與價目表 UI 入口；可把選取列、目前篩選結果或全部未定價價目匯出給 Excel 填價 |
| 已做 | 需重產工作隊列 | 材料補價完成訊息列出受影響報告；紀錄管理面板可快速篩選與匯出需重產清單；重新產出成功會清除舊重產旗標 |
| 已做 | 現場資料核心 Phase 0 起步 | 依 `09_現場資料核心與多格式輸出前導書.md` 新增 `canonical_report.py`，可由 records + attachments 建立 `CanonicalReportSet`，並提供 field-path catalog CLI |
| 已做 | 現場修改統計單第一版 | 新增純 openpyxl exporter 與 CLI，從 `CanonicalReportSet` 匯出總覽、修改單清單、焊口統計、照片索引、照片表、用料統計、問題清單；照片表會嵌入 before/after 圖片，紀錄管理面板新增入口 |
| 已做 | Template Mapping 驗證骨架 | 新增 `canonical_fields.py`、`template_mapping.py` 與 `tools/validate_template.py`；可驗證 `text / image / table` 三原語模板只引用 field-path catalog，並可依路徑解析 CanonicalReport 值 |
| 已做 | Template dry-run 預檢骨架 | 新增 `template_dry_run.py` 與 `tools/dry_run_template.py`；可在不產 Excel/PDF 前提下預覽欄位取值、圖片是否存在、表格列數與超出列數 |
| 已做 | xlsx_template renderer 第一版 | 新增 `xlsx_template_renderer.py` 與 `tools/render_xlsx_template.py`；可用 JSON template 寫入文字、嵌入圖片、展開表格，並支援既有 workbook 樣板 |
| 已做 | Checkpoint C C1 表格溢出回補 | `table` mapping 強制設定 `max_rows` 或 `rows_per_page`；超出列數時 dry-run 升級為 error，renderer 不產出會覆蓋版面的錯檔 |
| 已做 | Checkpoint C C3 孤兒資料報告 | dry-run 新增 `coverage.unmapped_data`，可列出 CanonicalReport 有值但模板未使用的欄位；支援 `coverage_ignore` 明確忽略非必要欄位 |
| 已做 | Checkpoint C C2 輸出後校驗 | xlsx renderer 產檔後重新讀取 workbook，校驗 text、image anchor 與 table cell；render result 會回報 `post_validation` |
| 已做 | Checkpoint C C4 xlsx 版面碰撞回補 | xlsx renderer render 前檢查 text/image/table 佔用 cell 區域是否重疊或超出 Excel 邊界；失敗時不產出 workbook |
| 已做 | Checkpoint C C6 照片路徑表示收斂 | field-path catalog 統一以 `photos.before[*]` / `photos.after[*]` 作為集合表示；`[0..n]` 僅保留為舊模板相容解析，不再由 `list-fields` 匯出 |
| 部分 | Checkpoint C C5 舊 COM 邊界收斂 | 已完成 P0 import 邊界：`excel_handler` lazy import COM、GUI/CLI 舊產出前做能力探測、無 COM 時停用舊產出且核心/GUI 可 import；仍待 renderer registry 與舊報表 canonical 化 |
| 部分 | Checkpoint C C5 renderer registry | 新增 renderer registry 與 `list_renderers`；`xlsx_template` 走 registry 分派，`xlsx_com` 登錄為 legacy optional 並阻擋 canonical adapter 未完成時的直出；仍待 GUI 全面改用 registry 與 COM adapter canonical 化 |
| 已做 | Checkpoint C C5 import-guard 正式鎖 | 新增正式 import-guard 測試，封鎖 `pythoncom/win32com` 後 import 核心與 GUI 啟動集合，確保 COM 不會回到啟動期依賴 |
| 部分 | Checkpoint C C5 GUI 讀 registry | GUI 舊產出狀態改讀 renderer registry；啟動時顯示 `unprobed` 不啟動 Excel，開始/重試時才完整 probe；仍待新增非 COM PDF 路線 |
| 部分 | 非 COM PDF 路線 | 新增 LibreOffice capability probe、workbook→PDF converter、CLI 與 `settings.json` 的 `soffice_path`；converter timeout/spawn failure 已轉結構化錯誤並嘗試終止程序樹；部署策略已決定 portable LibreOffice 優先、settings fallback、已安裝 LibreOffice 可容忍。仍待 portable 打包落地與 CJK/真機視覺驗證 |
| 已做 | pdf_overlay schema 閘門 | 新增 `pdf_overlay_schema.py`，`validate_template.py` 可驗證 PDF `page/rect_norm`、座標邊界、重疊、table row limit、欄寬與 Excel target 欄位誤用；renderer 已升級為 `minimal`，schema 閘門仍作為正式 render 前置檢查 |
| 已做 | output_result v1 envelope | 新增 `output_result.py`；`xlsx_template`、LibreOffice PDF converter、現場統計單 CLI 開始統一回 `result_schema_version / outputs / issues / capabilities / steps`，保留既有詳細欄位相容舊 UI |
| 已做 | Demo edge matrix 測試床 | `tools/run_demo_output_smoke.py --edge-matrix` 可建立含缺 after、材料超列、多照片超列、多頁 PDF、旋轉 base PDF 的 demo 專案；以 dry-run 驗證預期問題碼真的出現，供 pdf_overlay renderer 垂直切片使用 |
| 部分 | pdf_overlay renderer 最小垂直切片 | 新增 `pdf_overlay_renderer.py` 與 `tools/render_pdf_overlay.py`；registry 狀態升為 `minimal`，可疊 text/image/table/debug rect 到 base PDF，已補 CropBox、`/Rotate`、`text overflow=error` fail-fast 與 `table overflow=new_page`；`truncate` 仍明確 fail-fast，仍待多頁照片 grid、真實公司表單驗證 |
| 已做 | Demo smoke 人工測試入口 | `tools/run_demo_output_smoke.py` 可安全建立 `staging/demo_output` demo 專案，產出 CanonicalReportSet、範例 xlsx_template、範例 pdf_overlay template、模板 xlsx 與現場統計單 xlsx；有 marker 防止覆寫正式資料夾 |
| 已做 | 真 attachments showcase 入口 | 新增 `tools/run_real_attachments_showcase.py`，可用目前 `attachments/` 真資料輸出 CanonicalReportSet、現場統計單 Excel、PDF overlay 與可選 PNG；有 marker 防止誤覆寫，適合展示資料核心已接通 |
| 已做 | 多頁照片 grid | `pdf_overlay` table column 支援 `cell_type: image`，可用 `photos.before[*]` / `photos.after[*]` 產 before/after 照片表並沿用 `rows_per_page + overflow=new_page` 分頁；真 attachments showcase 已輸出 `real_photo_grid_{folder}.pdf` |
| 已做 | GUI 照片 PDF 入口 | 紀錄管理頁新增 `照片PDF` 按鈕，可一鍵用目前 `attachments/` 產出 CanonicalReportSet、現場統計單、summary PDF 與 photo grid PDF；輸出到 marker 保護的 `staging/real_attachments_showcase_gui` |
| 已做 | 照片 PDF 輸出範圍選擇 | `CanonicalReportSet` 與 showcase 支援指定 `(date, folder)`；GUI `照片PDF` 可選全部、目前篩選結果或選取修改單，CLI 支援 `--include DATE/FOLDER` |
| 已做 | 輸出中心內容選擇 | 紀錄管理頁入口改為 `輸出中心`，可勾選現場統計單 Excel、summary PDF、before/after 照片 PDF；CLI 支援 `--no-statistics`、`--no-summary-pdf`、`--no-photo-grid-pdf` |
| 已做 | 輸出中心位置選擇 | `輸出中心` 對話框可指定輸出資料夾並用瀏覽選擇；預設仍是 marker 保護的 `staging/real_attachments_showcase_gui`，既有非 showcase 資料夾仍拒絕覆寫 |
| 已做 | 輸出結果清單 | `輸出中心` 完成後顯示結果對話框，列出資料 JSON、統計單 Excel、摘要 JSON、summary PDF 與照片 PDF，可開啟選取檔案或輸出資料夾 |
| 已做 | Site Output Center 正式命名 | 新增 `site_output_center.py` 與 `tools/run_site_output_center.py`；GUI 改接正式入口，預設輸出到 `staging/site_output_center_gui`，正式檔名改為 `site_statistics.xlsx`、`site_summary_{folder}.pdf`、`site_photo_grid_{folder}.pdf` |
| 已做 | Site Output Runner 共用流程 | 新增 `site_output_runner.py`，正式輸出中心與 real attachments showcase 共用 CanonicalReport 收集、統計單、PDF render、summary result 流程，兩個入口只保留命名與 template 差異 |
| 已做 | GUI 輸出中心命名收斂 | 紀錄管理頁主路徑改用 `_output_center_*` helper 與輸出中心語意；保留 `_showcase_*` alias，避免舊測試或舊內部呼叫斷裂 |
| 已做 | 輸出中心結果清單分組 | 完成後結果 dialog 依主要輸出、PDF、資料檔、資料提醒分組；輸出列顯示可開啟、頁數、失敗 issue code 與找不到檔案狀態 |
| 已做 | 輸出中心資料提醒定位 | `CanonicalReportSet.issues` 補 `report_id/date/folder`；結果 dialog 的資料提醒與 PDF 列可定位回紀錄管理頁對應修改單 |
| 已做 | 輸出中心定位自動解除篩選 | 定位提醒或 PDF 對應修改單時，若目前清單被狀態/搜尋/日期篩選藏住，會自動切回全部並清空搜尋後重試定位 |
| 已做 | 輸出中心資料提醒處理入口 | 結果 dialog 新增 `處理提醒`；依 `note/before_photo/after_photo/parse_error/weld_or_material` 提供開附件資料夾或定位修改單動作 |
| 已做 | note 提醒內建編輯入口 | `note` 資料提醒升級為內建 `note.txt` 編輯視窗；儲存前擋空白/樣板文字，並以 `.tmp + os.replace` 寫回附件資料夾 |
| 已做 | 照片提醒接入加圖流程 | `before_photo/after_photo` 資料提醒改為直接開選圖流程，依提醒自動寫入 `before/after` 命名序列 |

## 暫不做

- 材料料庫完整 UI
- 請款批次完整流程
- 角色權限
- SQLite migration
- 中央伺服器
- PyInstaller 打包優化

## Phase 0 完成標準

- 模擬兩個程式同時開啟，不會互相覆蓋資料。
- 刪掉空資料夾時，工具能安全重建。
- 刪掉或破壞重要 JSON 時，工具不會直接覆蓋掉原資料。
- 程式中斷後重開，能辨識未完成操作。
- 健康檢查能把問題講成人話。
- 測試涵蓋正常、缺檔、壞檔、lock、備份、稽核。
