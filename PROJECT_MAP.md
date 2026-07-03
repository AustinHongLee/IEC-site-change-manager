# 管線修改單系統 — 專案總覽

> **最後更新**：2026-03-04  
> **Python 版本**：3.12（見 `.python-version`）  
> **GUI 框架**：PyQt6 6.10  
> **目前資料量**：171 筆紀錄 / 723 筆明細 / 174 份 PDF / 172 個資料夾（32 個日期）

---

## 📁 目錄結構與檔案歸屬

```
工務修改單/                          ← 專案根目錄
│
├── 啟動_新版GUI.bat                🟢 入口：新版主介面 GUI
├── .python-version                 🟢 鎖定 Python 3.12
├── requirements.txt                🟢 pip 依賴清單（純 ASCII）
├── settings.json                   🟢 使用者設定（路徑、欄位映射、執行參數）
├── .gitignore                      🟢 版本控制排除規則
├── README.md                       🟢 專案說明
├── PROJECT_MAP.md                  🟢 ← 本文件
│
├── DATA_FLOW_AUDIT.md              📄 過期文件（已被本文件取代）
│
├── control/                        🟢 全部原始碼（見下方模組清單）
├── tools/                          🟢 開發/維護工具（含一次性腳本與舊 launcher）
├── packaging/                      🟢 打包工具與 PyInstaller spec
├── tests/                          🟢 測試套件（100 個測試）
├── template/                       🟢 Excel 報告模板
├── records/                        🟢 JSON 資料儲存區
├── attachments/                    🟢 原始資料夾（before/after 照片 + 附件）
├── output/                         🟢 產出 Excel 報告（按日期分目錄）
├── pdf/                            🟢 產出 PDF 報告（扁平命名）
├── staging/                        🟢 暫存區（拍照後暫放）
├── logs/                           🟢 應用日誌（rotating file）
└── .venv/                          ⬜ 虛擬環境（自動建立）
```

---

## 📦 資料儲存區明細

### `records/` — JSON 主資料庫

| 檔案 | 角色 | 寫入者 | 讀取者 |
|------|------|--------|--------|
| `records.json` | **主紀錄 + 明細**（`records[]` + `details[]`） | `record_manager.py` | GUI 全域 |
| `billing.json` | 請款狀態與金額 | `gui_panels.py (BillingPanel)` | BillingPanel |
| `dwg_map.json` | DWG LIST 快取（serial → DWG NO 映射） | `record_manager.py` | `gui.py`, `wizard.py` |
| `weld_snapshot.json` | 焊口快照（重複性檢查用） | `gui_dialogs.py (WeldSnapshotManager)` | WeldDuplicateCheckDialog |
| `backups/` | `records.json` 自動備份（最多 5 份） | `record_manager.py` | 手動還原 |
| `records.json.bak.*` | 即時備份（寫入前自動產生） | `record_manager.py` | 手動還原 |
| `管線修改紀錄清單_*.xlsx` | 匯出的 Excel 格式紀錄（3-sheet） | `record_manager.py` | 外部使用 |

### `attachments/` — 原始工作資料

```
attachments/
├── _archived/              ← 已歸檔（從 GUI 右鍵移入）
│   └── YYYYMMDD/{folder}/
├── YYYYMMDD/               ← 日期目錄（如 20260303）
│   ├── {serial}_{codes}/   ← single 模式（如 72_11r2）
│   │   ├── before.jpg      必要：施工前照片
│   │   ├── after.jpg       必要：施工後照片
│   │   ├── note.txt        可選：修改說明
│   │   ├── materials.txt   可選：材料清單
│   │   ├── weld_info.json  可選：焊口詳細資料（材質/厚度）
│   │   └── *.pdf           可選：附件圖面
│   └── {serial}_AG/        ← group 模式
│       ├── GroupWeld.txt   必要：焊口清單
│       ├── before_1.jpg    必要：各焊口施工前
│       ├── after_1.jpg     必要：各焊口施工後
│       ├── before_2.jpg    …
│       ├── after_2.jpg     …
│       ├── note.txt        可選
│       ├── materials.txt   可選
│       ├── weld_info.json  可選
│       └── *.pdf           可選
```

### `output/` — Excel 產出

```
output/YYYYMMDD/{serial}_{codes}.xlsm   ← 填好的報告 Excel
```

### `pdf/` — PDF 產出（扁平結構）

```
pdf/YYYYMMDD-NN.pdf    ← 報告編號即檔名（如 20260303-01.pdf）
```

### `template/` — 報告模板

| 檔案 | 用途 |
|------|------|
| `template_file.xlsm` | 標準 6-slot 模板（≤6 焊口） |
| `template_file_27w.xlsm` | 27-slot 模板（>6 焊口或 group 模式） |
| `template_file.xlsx` | 備份/舊版模板 |

---

## 🧩 模組架構圖

```
啟動_新版GUI.bat
    │
    ▼
main.py ─────────┬──→ gui.py (MainWindow)
  │  (--cli)     │        │
  │              │        ├── Tab 1: 報告產出
  ▼              │        │     └── _process_folders()
run_cli()        │        │           ├── parsers.parse_folder()
  │              │        │           ├── excel_handler.generate_report()
  ├── parsers    │        │           ├── image_processor.*
  ├── excel_handler       │           ├── record_manager.upsert_*
  ├── utils      │        │           └── utils.compute_fingerprint()
  ├── record_manager      │
  └── weld_control        ├── Tab 2: 紀錄管理 (gui_panels.RecordManagerPanel)
                 │        │     ├── 焊口明細（inline 編輯）
                 │        │     ├── 材料明細（inline 編輯）
                 │        │     ├── 圖片預覽（hover zoom）
                 │        │     ├── 右鍵：開啟/編輯/歸檔/還原/補登
                 │        │     └── 儲存 → record_manager + weld_info.json
                 │        │
                 │        ├── Tab 3: 請款管理 (gui_panels.BillingPanel)
                 │        │     ├── 狀態追蹤（未請款/已請款/已結案/暫緩）
                 │        │     ├── 金額 inline 編輯
                 │        │     ├── 統計卡片（即時計算）
                 │        │     └── 匯出報表 / 匯出請款單
                 │        │
                 │        └── Tab 4: 設定 (gui_settings.SettingsPanel)
                 │              ├── 焊口管制表設定（路徑/表頭/動態欄位/測試連線）
                 │              ├── DWG LIST 設定（路徑/表頭/動態欄位）
                 │              ├── 預製圖目錄設定
                 │              ├── 執行參數（圖片預處理/完整性檢查等級）
                 │              └── 關於
                 │
                 └── gui_dialogs.py（獨立對話框）
                       ├── WeldBackfillDialog      焊口補登工具
                       ├── WeldDuplicateCheckDialog 焊口重複性檢查
                       ├── SupplementInfoDialog     補充資料夾資訊
                       ├── EditRecordDialog         編輯記錄（改焊口/尺寸/重命名）
                       ├── WeldSnapshotManager      焊口快照管理（純邏輯）
                       └── RecordManagerDialog      ⚠️ 已棄用

wizard.py ← 從 Tab 1 啟動
    ├── Step 1: 日期 + 流水號
    ├── Step 2: 模式選擇 (single/group)
    ├── Step 3: 焊口輸入（重複檢查 + 管制表查詢 + 排序）
    ├── Step 4: 照片選取（含 staging 整合 + hover zoom）
    ├── Step 5: 修改原因說明（預設語句 + 歷史記錄）
    ├── Step 6: 材料清單
    ├── Step 7: 確認 + 建立
    └── HistorySidebar: 流水號歷史（before/after/PDF 預覽）
```

---

## 🔧 control/ 模組清單（21 檔）

### 核心模組（正式使用中）

| 模組 | 行數 | 角色 | 依賴 |
|------|------|------|------|
| `main.py` | 325 | CLI/GUI 入口調度 | config, parsers, utils, record_manager, excel_handler, gui |
| `config.py` | 176 | 全域常數 + 路徑 + RuntimeConfig | settings_manager |
| `parsers.py` | 318 | 資料夾名稱/焊口碼解析 | (無外部依賴) |
| `utils.py` | 485 | 通用工具（模糊欄位匹配/Excel 安全讀寫/PDF 合併/指紋） | config |
| `validator.py` | 697 | 資料夾格式驗證 | parsers |
| `image_processor.py` | 410 | 照片預處理（EXIF 修正/縮放） | Pillow |
| `excel_handler.py` | 356 | Excel COM 操作（填表/插圖/匯出 PDF） | config, parsers, utils, pywin32 |
| `record_manager.py` | 769 | 紀錄 CRUD + DWG 快取 + 自動備份 + Excel 匯出 | config, utils |
| `settings_manager.py` | 361 | settings.json 讀寫（單例） | (無外部依賴) |
| `staging_manager.py` | 391 | Staging 區管理（掃描/分群/分派） | Pillow |
| `weld_control.py` | 1332 | 焊口管制表管理（JSON 快取 + O(1) 查詢） | settings_manager, utils |
| `log_config.py` | 117 | 統一日誌配置（console + rotating file） | (標準庫) |
| `theme.py` | 575 | 全域 QSS 主題 + 色盤 + 字體 + 元件工廠 | PyQt6 |

### GUI 模組

| 模組 | 行數 | 角色 |
|------|------|------|
| `gui.py` | 1003 | 主視窗 MainWindow + 4-tab 架構 |
| `gui_panels.py` | 1699 | RecordManagerPanel + BillingPanel |
| `gui_settings.py` | 1120 | SettingsPanel + HelpTooltip 系統 |
| `gui_dialogs.py` | 2021 | 6 個對話框（補登/快照/重複檢查/補充/編輯/紀錄管理） |
| `wizard.py` | 2277 | 7 步驟精靈 + HistorySidebar + StagingPicker |

### 非核心 / 工具

| 模組 | 行數 | 狀態 | 說明 |
|------|------|------|------|
| `Product_report_.py` | 1463 | ⛔ **已棄用** | 舊版單體腳本，`__main__` 已阻止執行 |
| `debug_backfill.py` | 236 | 🔧 debug 工具 | 焊口補登邏輯測試，未被 import |
| `debug_excel.py` | 91 | 🔧 debug 工具 | Excel 結構檢視，未被 import |
| `wizard_data.json` | — | 🟢 資料檔 | 精靈預設語句 + 材料選項 |
| `MODULE_MAP.md` | 78 | ⚠️ **過期** | 已被 PROJECT_MAP.md 取代 |

### 備份目錄

| 目錄 | 說明 |
|------|------|
| `control/tkinter_backup/` | 舊版 tkinter GUI 備份（5 檔），已完全被 PyQt6 取代 |
| `control/__pycache__/` | Python 快取 |

---

## 🔬 完整功能清單

### A. 報告產出流程

| # | 功能 | 位置 | 說明 |
|---|------|------|------|
| A1 | 日期資料夾掃描 | `gui.py` `_load_initial_data()` | 列出 attachments/ 下所有日期 |
| A2 | 資料夾列表右鍵選單 | `gui.py` `_show_date_context_menu()` | 開啟資料夾/勾選/取消 |
| A3 | 日期全選/取消全選 | `gui.py` `_select_all()` `_deselect_all()` | |
| A4 | 資料夾子選篩選 | `gui.py` `_show_folder_selector()` | 選擇特定日期下的資料夾 |
| A5 | DWG LIST 載入 | `gui.py` `_browse_dwg_list()` | 瀏覽選取 + 自動搜尋 |
| A6 | 批次報告產出 | `gui.py` `_process_folders()` | 背景執行緒 + 進度條 |
| A7 | 指紋比對跳過 | `gui.py` `_process_folders()` | 未變更的資料夾自動跳過 |
| A8 | 失敗重試 | `gui.py` `_retry_failed()` | 重試失敗項目 |
| A9 | 中止處理 | `gui.py` `_stop_processing()` | 中途停止 |
| A10 | 開啟 PDF/output 目錄 | `gui.py` `_open_pdf_folder()` `_open_output_folder()` | |
| A11 | 資料夾驗證 | `gui.py` `_validate_folders()` | 檢查命名/照片/PDF 是否齊全 |
| A12 | 批次圖片預處理 | `gui.py` `_preprocess_images()` | EXIF 修正 + 縮放 |
| A13 | 補充資訊填寫 | `gui.py` `_supplement_info()` → `SupplementInfoDialog` | 填材質/厚度 |
| A14 | 焊口重複性檢查 | `gui.py` `_open_weld_duplicate_check()` | |

### B. 前置作業精靈

| # | 功能 | 位置 | 說明 |
|---|------|------|------|
| B1 | 日期 + 流水號設定 | `wizard.py` `Step1_DateSeries` | 日曆選取 + 手動輸入 |
| B2 | 模式選擇 | `wizard.py` `Step2_Mode` | single / group 視覺化選取 |
| B3 | 焊口輸入 | `wizard.py` `Step3_Welds` | 多列表單 + 驗證 |
| B4 | 焊口重複即時檢查 | `wizard.py` `Step3_Welds` | ⚡ 即時查管制表 |
| B5 | 焊口排序/上下移動 | `wizard.py` `Step3_Welds` | 調整順序 |
| B6 | 照片選取（檔案瀏覽） | `wizard.py` `Step4_Images` | 標準檔案選取對話框 |
| B7 | Staging 照片選取 | `wizard.py` `Step4_Images` → `StagingPickerDialog` | staging 縮圖視覺化選取 |
| B8 | Staging 縮圖 hover zoom | `wizard.py` `_StagingThumb` `_ZoomPopup` | 320px 預覽浮窗 |
| B9 | Staging 清空按鈕 | `wizard.py` `StagingPickerDialog._cleanup_staging()` | 一鍵刪除 |
| B10 | 修改原因說明 | `wizard.py` `Step5_Note` | 文字輸入 |
| B11 | 預設語句快選 | `wizard.py` `Step5_Note` | 4 類預設 + 點擊插入 |
| B12 | 歷史說明複製 | `wizard.py` `Step5_Note` | 從歷史記錄選取 |
| B13 | 材料清單填寫 | `wizard.py` `Step6_Materials` | 零件/尺寸/材質/數量 |
| B14 | 確認 + 建立資料夾 | `wizard.py` `Step7_Confirm` → `_create_folder()` | |
| B15 | 自動寫入焊口管制表 | `wizard.py` `_write_welds_to_control_table()` | 可選功能 |
| B16 | Staging 原始檔清理 | `wizard.py` `_create_folder()` | 建立後詢問刪除 staging |
| B17 | 歷史側邊欄 | `wizard.py` `_HistorySidebar` | 290px 可摺疊 |
| B18 | 歷史 before/after/PDF 縮圖 | `wizard.py` `_HistoryThumb` | hover 放大 |
| B19 | PDF 第一頁渲染 | `wizard.py` `_render_pdf_page()` | PyMuPDF |

### C. 紀錄管理

| # | 功能 | 位置 | 說明 |
|---|------|------|------|
| C1 | 紀錄列表顯示 | `gui_panels.py` `RecordManagerPanel.load_records()` | |
| C2 | 搜尋篩選 | `gui_panels.py` `RecordManagerPanel._build_ui()` | 文字搜尋 |
| C3 | 焊口明細 tab | `gui_panels.py` `_update_detail_data()` | inline 雙擊編輯 |
| C4 | 材料明細 tab | `gui_panels.py` `_update_material_data()` | inline 雙擊編輯 |
| C5 | 圖片明細 tab | `gui_panels.py` `_update_image_detail()` | before/after/PDF 縮圖 |
| C6 | 圖片 hover zoom | `gui_panels.py` `_HoverThumb` `_ZoomLabel` | 140px→380px |
| C7 | 圖片替換 | `gui_panels.py` `_replace_image()` | 右鍵替換 |
| C8 | 圖片新增 | `gui_panels.py` `_add_image()` | 新增照片 |
| C9 | PDF 第一頁縮圖 | `gui_panels.py` `_render_pdf_thumb()` | PyMuPDF |
| C10 | 右鍵：開啟資料夾 | `gui_panels.py` `_open_folder_for()` | |
| C11 | 右鍵：開啟 PDF | `gui_panels.py` `_open_pdf_for()` | |
| C12 | 右鍵：編輯紀錄 | `gui_panels.py` `_edit_record()` → `EditRecordDialog` | |
| C13 | 右鍵：歸檔 | `gui_panels.py` `_archive_record()` | 移至 `_archived/` |
| C14 | 右鍵：還原歸檔 | `gui_panels.py` `_restore_record()` | 從 `_archived/` 移回 |
| C15 | 右鍵：補登工具 | `gui_panels.py` `_open_backfill_tool()` | |
| C16 | 儲存變更 | `gui_panels.py` `_save_changes()` | 同步 records.json + weld_info.json |
| C17 | 開啟資料夾/PDF/Excel | `gui_panels.py` 按鈕列 | |
| C18 | 未產出標記 | `gui_panels.py` `load_records()` | 掃描 attachments 找無對應紀錄的 |
| C19 | 歸檔項目顯示 | `gui_panels.py` `load_records()` | 掃描 `_archived/` |

### D. 請款管理

| # | 功能 | 位置 | 說明 |
|---|------|------|------|
| D1 | 請款列表 | `gui_panels.py` `BillingPanel.load_data()` | 合併 records + billing |
| D2 | 日期/狀態篩選 | `gui_panels.py` `_apply_filter()` | |
| D3 | 狀態 inline 編輯 | `gui_panels.py` `_on_double_click()` | ComboBox 下拉 |
| D4 | 日期/金額 inline 編輯 | `gui_panels.py` `_on_double_click()` | |
| D5 | 統計卡片 | `gui_panels.py` `_update_statistics()` | 總金額/已請款/未請款/暫緩 |
| D6 | 匯出統計報表 | `gui_panels.py` `_export_report()` | 含合計列的 Excel |
| D7 | 匯出請款單 | `gui_panels.py` `_export_billing()` | 未請款項目 + 簽核區 |
| D8 | 儲存請款狀態 | `gui_panels.py` `_save_changes()` | billing.json |

### E. 設定管理

| # | 功能 | 位置 | 說明 |
|---|------|------|------|
| E1 | 焊口管制表路徑設定 | `gui_settings.py` `_browse_weld_table()` | |
| E2 | 管制表連線測試 | `gui_settings.py` `_test_weld_table()` | 讀取表頭驗證 |
| E3 | 動態欄位 CRUD | `gui_settings.py` `_add/edit/delete_dynamic_column()` | |
| E4 | 從 Excel 匯入欄位 | `gui_settings.py` `_load_excel_columns()` | 自動偵測表頭 |
| E5 | DWG LIST 設定 | `gui_settings.py` `_browse_dwg_list()` | |
| E6 | DWG LIST 連線測試 | `gui_settings.py` `_test_dwg_list()` | |
| E7 | DWG 動態欄位 CRUD | `gui_settings.py` `_add/edit/delete_dwg_dynamic_column()` | |
| E8 | 預製圖目錄設定 | `gui_settings.py` `_browse_prefab_dir()` | |
| E9 | 執行參數調整 | `gui_settings.py` `_build_runtime_tab()` | 圖片/完整性/PDF |
| E10 | 恢復預設值 | `gui_settings.py` `_reset_defaults()` | |
| E11 | Help tooltip 系統 | `gui_settings.py` `HelpTooltip` | ❓ 可點擊說明 |

### F. 焊口管理工具

| # | 功能 | 位置 | 說明 |
|---|------|------|------|
| F1 | 焊口補登掃描 | `gui_dialogs.py` `WeldBackfillDialog._scan_missing_welds()` | |
| F2 | 補登篩選（日期/流水號） | `gui_dialogs.py` `_apply_filter()` | |
| F3 | 批次勾選（全選/反選） | `gui_dialogs.py` `_select_all()` 等 | |
| F4 | 補登寫入（另存新檔） | `gui_dialogs.py` `_write_selected()` | 不覆蓋原檔 |
| F5 | 焊口快照建立 | `gui_dialogs.py` `WeldSnapshotManager.build_snapshot()` | |
| F6 | 重複性檢查 | `gui_dialogs.py` `WeldDuplicateCheckDialog._check_duplicates()` | |
| F7 | 重複項封存 | `gui_dialogs.py` `_archive_selected_folder()` | |
| F8 | 匯出重複報告 | `gui_dialogs.py` `_export_report()` | |
| F9 | 查看現有焊口 | `wizard.py` `_show_welds_dialog()` | 同義字模糊匹配 |

### G. 資料夾編輯

| # | 功能 | 位置 | 說明 |
|---|------|------|------|
| G1 | 編輯焊口/尺寸 | `gui_dialogs.py` `EditRecordDialog._save_changes()` | |
| G2 | 資料夾自動重命名 | `gui_dialogs.py` `EditRecordDialog._save_changes()` | 依新焊口碼更新名稱 |
| G3 | weld_info.json 同步 | `gui_dialogs.py` `EditRecordDialog._save_changes()` | |
| G4 | GroupWeld.txt 同步 | `gui_dialogs.py` `EditRecordDialog._save_changes()` | |
| G5 | 補充資料夾資訊 | `gui_dialogs.py` `SupplementInfoDialog` | 材質/厚度填寫 |
| G6 | 管制表參考查詢 | `gui_dialogs.py` `SupplementInfoDialog._load_reference_data()` | |
| G7 | 相同尺寸自動配對 | `gui_dialogs.py` `SupplementInfoDialog._copy_matching_size()` | |
| G8 | 快速填充 | `gui_dialogs.py` `SupplementInfoDialog._apply_quick_fill()` | |

### H. 底層服務

| # | 功能 | 位置 | 說明 |
|---|------|------|------|
| H1 | 資料夾名稱解析 | `parsers.py` `parse_folder()` | single/group 偵測 + 焊口碼拆分 |
| H2 | GroupWeld.txt 解析 | `parsers.py` `read_groupweld_txt()` | 新/舊格式支援 |
| H3 | note.txt / materials.txt | `parsers.py` `read_note_and_materials()` | |
| H4 | 自動說明文字產生 | `parsers.py` `build_auto_description()` | |
| H5 | Excel COM 單例 | `excel_handler.py` `ExcelManager` | lazy init + auto-reconnect |
| H6 | 模板填表 + 插圖 | `excel_handler.py` `generate_report()` | |
| H7 | PDF 匯出（含重試） | `excel_handler.py` `export_pdf_with_retry()` | |
| H8 | PDF 合併 | `utils.py` `merge_into_second_page()` | 附件插至第 2 頁 |
| H9 | 內容指紋計算 | `utils.py` `compute_fingerprint()` | MD5 綜合 |
| H10 | 完整性檢查（3 級） | `utils.py` `check_integrity()` | |
| H11 | 焊口管制表快取 | `weld_control.py` `WeldControlManager` | Excel→JSON 快取 + mtime |
| H12 | 焊口 O(1) 查詢 | `weld_control.py` `check_exists()` | |
| H13 | 焊口批次新增 | `weld_control.py` `add_welds_batch()` | 含回寫 Excel |
| H14 | 同義字欄位匹配 | `utils.py` `resolve_col()` `resolve_col_map()` | 焊↔銲 |
| H15 | 報告編號對照表 | `weld_control.py` `build_report_id_lookup()` | 從 records.json 讀取 |
| H16 | DWG LIST 快取 | `record_manager.py` `load_drawing_map()` | JSON 快取 + mtime |
| H17 | 自動備份 | `record_manager.py` `auto_backup()` | 寫入前自動備份 |
| H18 | Excel→JSON 遷移 | `record_manager.py` `migrate_excel_to_json()` | |
| H19 | 專業 Excel 匯出 | `record_manager.py` `export_records_to_excel()` | 3-sheet + 排版 |
| H20 | Staging 掃描/分群 | `staging_manager.py` `scan_staging()` `group_by_time()` | |
| H21 | Staging 分派 | `staging_manager.py` `dispatch_files()` | copy/move |
| H22 | 圖片預處理 | `image_processor.py` `preprocess_single_image()` | EXIF + 縮放 |
| H23 | 預製圖自動複製 | `utils.py` `copy_prefab_pdf()` | |
| H24 | 日誌系統 | `log_config.py` `setup_logging()` | rotating file + console |
| H25 | QSS 主題系統 | `theme.py` `build_stylesheet()` `apply_theme()` | |

---

## ⚠️ 風險評估

### 🔴 高風險

| 風險 | 說明 | 影響 | 建議 |
|------|------|------|------|
| **根目錄舊 Excel** | `管線修改紀錄清單.xlsx` 仍存在根目錄 | 使用者可能誤以為是主資料來源 | 移至 `records/` 或刪除 |
| **重複邏輯** | `main.py.run_cli()` ≈ `gui.py._process_folders()` ~200 行幾乎相同 | 改一處忘另一處 | 抽取共用函式 |
| **重複邏輯** | `_build_detail_row()` 在 main.py 和 gui.py 各有一份 | 同上 | 移至 utils.py |
| **Product_report_ 未遷移** | `parse_materials_txt()` + `upsert_materials_rows()` 僅存於已棄用檔案 | 材料同步功能缺失 | 遷移至 record_manager.py |
| **billing.json 非原子寫入** | `BillingPanel._save_billing_json()` 直接覆蓋 | 寫入中斷可能損壞 | 改用 atomic pattern |

### 🟡 中風險

| 風險 | 說明 | 影響 | 建議 |
|------|------|------|------|
| **settings.json 絕對路徑** | 路徑含磁碟代號 | 跨機器/磁碟代號變更會壞 | 改存相對路徑 |
| **無檔案鎖** | GUI + CLI 或多機同時存取 | records.json 覆蓋風險 | Google Drive 已有衝突處理，但建議加 lockfile |
| **一次性腳本在根目錄** | 已移至 `tools/refresh_fp.py`、`tools/audit_data.py` | 根目錄雜亂 | 已整理 |
| **過期文件** | `MODULE_MAP.md` `DATA_FLOW_AUDIT.md` 內容已過時 | 誤導開發者 | 刪除或標記取代 |
| **Zoom 實作重複** | `_ZoomLabel`(gui_panels) vs `_ZoomPopup`(wizard) | 維護兩套 hover zoom | 統一至 theme.py |
| **tkinter 備份** | `control/tkinter_backup/` 仍存在 | 佔空間 | 確認不再需要後刪除 |

### 🟢 低風險

| 風險 | 說明 |
|------|------|
| PyMuPDF 三處獨立 try/except import | 功能正常但程式碼重複 |
| `RecordManagerDialog` 已棄用但仍佔 ~300 行 | 不影響功能但增加維護成本 |
| debug_*.py 未清理 | 不影響功能 |

---

## 🔄 資料流向簡圖

```
                                   settings.json
                                       │
                    ┌──────────────────┼──────────────────┐
                    ▼                  ▼                  ▼
            焊口管制表.xlsx      DWG LIST.xlsx      預製圖目錄/
            (外部 Excel)        (外部 Excel)        (附件 PDF)
                 │                    │                  │
                 ▼                    ▼                  ▼
         weld_control.py      record_manager.py      utils.py
         (.weld_cache/)       (dwg_map.json)      (copy_prefab)
                 │                    │
   ┌─────────────┴────────┐          │
   ▼                      ▼          ▼
wizard.py             gui.py    excel_handler.py
(寫入管制表)      (_process_folders)  (COM Excel)
   │                      │          │
   ▼                      ▼          ▼
attachments/          records.json   output/ + pdf/
(mkdir + 寫檔)        (upsert)       (xlsm + pdf)
```

---

## 📋 測試涵蓋

| 測試檔 | 數量 | 涵蓋模組 |
|--------|------|----------|
| `test_parsers.py` | — | parsers.py 全功能 |
| `test_utils.py` | — | utils.py 全功能 |
| `test_record_manager.py` | — | record_manager.py CRUD + 匯出 |
| `test_staging_manager.py` | — | staging_manager.py 掃描/分派 |
| **合計** | **100** | 涵蓋核心邏輯；GUI/Excel COM 未測試 |

---

## 📝 建議的清理行動

| 優先 | 行動 | 說明 |
|------|------|------|
| P1 | 移動/刪除根目錄 `管線修改紀錄清單.xlsx` | 避免混淆主資料來源 |
| P1 | 抽取 `_process_folders()` 共用邏輯 | 消除 main.py ↔ gui.py 重複 |
| P2 | 遷移 `parse_materials_txt()` + `upsert_materials_rows()` | 從 Product_report_ 搬至 record_manager |
| P2 | billing.json 改用原子寫入 | `_save_billing_json()` 加 `.tmp` + `os.replace()` |
| P3 | 一次性腳本移至 `tools/` | `tools/refresh_fp.py`, `tools/audit_data.py` |
| P3 | 刪除過期文件 | `MODULE_MAP.md`, `DATA_FLOW_AUDIT.md` |
| P3 | 統一 Zoom 元件 | 合併 `_ZoomLabel` / `_ZoomPopup` |
| P4 | 評估刪除 `tkinter_backup/` | 已完全不用 |
| P4 | 評估刪除 `Product_report_.py` | 遷移後可移除 |
| P4 | 清除 `RecordManagerDialog` | 已棄用的對話框 |
