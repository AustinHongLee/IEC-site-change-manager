# 資料流全圖 & 完整性審計報告

> 產出日期：2026-03-03（掃描） → 2026-03-04（修復 & 更新）  
> 掃描範圍：`control/` 全部 20 模組 + 根目錄腳本 + 5 個 JSON 資料庫 + attachments 全遍歷

---

## 目錄

1. [全局資料流架構圖](#1-全局資料流架構圖)
2. [資料存儲總覽](#2-資料存儲總覽)
3. [各模組讀寫矩陣](#3-各模組讀寫矩陣)
4. [交叉參照關係](#4-交叉參照關係)
5. [完整性掃描結果](#5-完整性掃描結果)
6. [風險評估](#6-風險評估)
7. [延伸建議](#7-延伸建議)

---

## 1. 全局資料流架構圖

```
                              ┌──────────────┐
                              │ settings.json │ ← 用戶設定（路徑/選項）
                              └──────┬───────┘
                                     │ 被所有模組讀取
                                     ▼
 ┌─────────┐   dispatch    ┌─────────────────────────────┐
 │ staging/ │ ──────────── │  attachments/{date}/{folder} │
 └─────────┘               │  ├── before.jpg / after.jpg  │
                            │  ├── before_1.jpg (AG 多圖)  │
      ┌──── wizard ────────▶│  ├── GroupWeld.txt           │
      │    (建立新案)        │  ├── note.txt / materials.txt│
      │                     │  ├── weld_info.json          │
      │                     │  ├── *.pdf (ISO圖/預製圖)     │
      │                     │  └── _ERROR.txt (錯誤標記)    │
      │                     └────────────┬────────────────┘
      │                                  │ 被讀取
      │         ┌────────────────────────┼────────────────────────┐
      │         ▼                        ▼                        ▼
      │   ┌──────────┐          ┌──────────────┐         ┌──────────────┐
      │   │ parsers  │          │image_processor│         │  validator   │
      │   │ 解析文字  │          │ 圖片預處理    │         │  資料驗證    │
      │   └────┬─────┘          └──────┬───────┘         └──────────────┘
      │        │                       │
      │        ▼                       ▼
      │   ┌─────────────────────────────────┐     ┌───────────────────┐
      │   │   gui.py / main.py (處理引擎)    │────▶│   excel_handler   │
      │   │   ├── compute_fingerprint()      │     │ (COM Automation)  │
      │   │   ├── preload_record_index()     │     │  ├── template/*.xlsm (讀)
      │   │   └── generate_report()          │     │  ├── output/{date}/*.xlsm (寫)
      │   └────────────┬────────────────────┘     │  └── pdf/{id}.pdf (寫)
      │                │                          └───────────────────┘
      │                ▼
      │   ┌─────────────────────────┐     ┌─────────────────────┐
      │   │  records/records.json   │     │  records/dwg_map.json│
      │   │  ├── records[] (171筆)  │     │  (DWG LIST 快取)     │
      │   │  ├── details[] (729筆)  │     └──────────┬──────────┘
      │   │  └── meta{}             │                │
      │   └───────────┬─────────────┘     ┌──────────▼──────────┐
      │               │                   │ DWG LIST Excel (外部)│
      │               ▼                   └─────────────────────┘
      │   ┌───────────────────────┐
      │   │ records/billing.json  │  (請款追蹤 — 目前為空)
      │   └───────────────────────┘
      │
      │   ┌────────────────────────────┐    ┌─────────────────────┐
      │   │records/weld_snapshot.json   │    │ 焊口管制表 Excel(外部)│
      │   │ (焊口快照 — 重複性檢查用)   │◀───│  └── .weld_cache/    │
      │   └────────────────────────────┘    └─────────────────────┘
      │                                              ▲
      └────── wizard_data.json (精靈歷史)             │
                                              weld_control.py
```

---

## 2. 資料存儲總覽

### 2.1 JSON 資料庫（專案內）

| 檔案 | 大小 | 角色 | 寫入模組 | 讀取模組 |
|------|------|------|----------|----------|
| `records/records.json` | 171 records, 729 details | **主記錄庫** | record_manager, _refresh_fp | record_manager, gui_panels, gui_dialogs, weld_control |
| `records/dwg_map.json` | 5 entries | DWG 對照快取 | record_manager | record_manager |
| `records/weld_snapshot.json` | 161 folders, 644 welds | 焊口快照 | gui_dialogs | gui_dialogs |
| `records/billing.json` | 空 | 請款追蹤 | gui_panels | gui_panels |
| `settings.json` | — | 用戶設定 | settings_manager, gui_settings | **幾乎全部模組** |
| `control/wizard_data.json` | — | 精靈預設 | wizard | wizard |

### 2.2 檔案系統結構

| 路徑 | 用途 | 實際數量 |
|------|------|----------|
| `attachments/{date}/{folder}/` | 附件資料夾（照片/PDF/文字） | **172 個資料夾** |
| `attachments/_archived/` | 全域歸檔 | 1 日期 (20260116) |
| `attachments/{date}/_archived/` | 日期層歸檔 | 有些日期底下有 |
| `output/{date}/` | 產出的 XLSM 報告 | 對應每個日期 |
| `pdf/` | 產出的 PDF 報告 | 171 個 PDF |
| `staging/` | 收件匣（暫存區） | 動態 |
| `template/` | Excel 模板 | 2 個 .xlsm |
| `records/backups/` | records.json 備份 | 保留最近 5 個 |
| `logs/` | 應用程式日誌 | rotating |

### 2.3 外部檔案（由 settings.json 指向）

| 設定鍵 | 用途 | 讀寫模組 |
|--------|------|----------|
| `paths.drawing_list` | DWG LIST 圖號清單 | record_manager (唯讀) |
| `paths.weld_control_table` | 焊口管制表 | weld_control (讀寫) |
| `paths.prefab_drawing_dir` | 預製圖目錄 | utils (唯讀) |

---

## 3. 各模組讀寫矩陣

> R = 讀取, W = 寫入, RW = 讀寫

| 模組 | records.json | dwg_map | weld_snap | billing | settings | attachments/ | output/ | pdf/ | 焊口管制表 | DWG LIST |
|------|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **config** | | | | | R | | | | | |
| **settings_manager** | | | | | RW | | | | | R |
| **record_manager** | RW | RW | | | R | | | | | R |
| **staging_manager** | | | | | | W | | | | |
| **parsers** | | | | | | R | | | | |
| **utils** | | | | | | RW | | RW | | |
| **excel_handler** | | | | | R | R | W | W | | |
| **image_processor** | | | | | | RW | | | | |
| **weld_control** | R | | | | R | R | | | RW | |
| **validator** | | | | | | R | | | | |
| **gui** | RW | | | | R | RW | W | | | |
| **gui_panels** | RW | | | RW | | R | | R | | |
| **gui_dialogs** | | | RW | | R | RW | | | RW | |
| **gui_settings** | | | | | RW | | | | R | R |
| **wizard** | | | | | | W | | | | |
| **main** | RW | | | | R | RW | W | | | |
| **_refresh_fp** | RW | | | | | R | | | | |
| **Product_report_** ⚠️ | | | | | | RW | W | W | | R |

---

## 4. 交叉參照關係

### 4.1 核心鏈結圖

```
records.json                          attachments/
├── records[].日期 ──────────────────▶ {日期}/
├── records[].資料夾名 ──────────────▶ {日期}/{資料夾名}/
├── records[].before.jpg ◀── 應反映 ── {folder}/before.jpg 是否存在
├── records[].after.jpg  ◀── 應反映 ── {folder}/after.jpg 是否存在
├── records[].內容指紋   ◀── 計算自 ── {folder}/ 內所有檔案的 MD5
├── records[].附件PDF    ◀── 應對應 ── {folder}/*.pdf
├── records[].報告編號   ──────────────▶ pdf/{報告編號}.pdf
│                        ──────────────▶ output/{日期}/管線修改單_*.xlsm
├── details[].紀錄編號   ──► 必須存在於 records[].報告編號
└── details[].Series NO  ──► 應一致於 records[].Series NO

dwg_map.json
└── map[series_no]       ◀── 快取自 ── DWG LIST Excel (用 mtime 驗證)

weld_snapshot.json
├── folders{}            ◀── 掃描自 ── attachments/ 全遍歷
└── weld_index{}         ◀── 擷取自 ── {folder}/weld_info.json + GroupWeld.txt

settings.json
├── paths.drawing_list   ──▶ DWG LIST Excel 絕對路徑
├── paths.weld_control_table ──▶ 焊口管制表 Excel 絕對路徑
└── paths.prefab_drawing_dir ──▶ 預製圖目錄絕對路徑
```

### 4.2 資料完整性約束

| 約束 | 來源 | 目標 | 強制性 |
|------|------|------|--------|
| `records[].日期+資料夾名` → 實體資料夾 | records.json | attachments/ | ❌ 未強制 |
| `records[].報告編號` 唯一性 | records.json 內部 | — | ❌ 邏輯假設 |
| `details[].紀錄編號` → records[]`.報告編號` | details | records | ❌ 未強制 |
| `before.jpg/after.jpg` 欄位 → 實體檔案 | records.json | attachments/ | ❌ 未強制 |
| `dwg_map` mtime → DWG LIST | dwg_map.json | 外部 Excel | ✅ 有驗證 |
| `weld_snapshot` → attachments | snapshot | attachments/ | ❌ 手動重建 |

---

## 5. 完整性掃描結果

> 初掃描：2026-03-03 23:55  
> 修復後：2026-03-04 00:20  
> records.json: 171 records, **723 details** (清理後), 172 actual folders

### ✅ 通過

| 檢查項 | 結果 |
|--------|------|
| Records → Attachments 資料夾對應 | **0 筆** 不一致（已清理 3 筆幽靈紀錄）|
| 報告編號唯一性 | **0 筆** 重複 |
| (日期, 資料夾名) 主鍵唯一性 | **0 筆** 重複 |
| PDF 產出完整性 | **0 筆** 缺 PDF |
| details → records 參照完整性 | **0 筆** 孤立 ✅ *（2026-03-04 修復）* |
| _ERROR.txt 殘留 | **0 筆** ✅ *（2026-03-04 清除）* |
| Weld snapshot 同步 | **171 folders, 671 welds** ✅ *（2026-03-04 重建）* |

### ℹ️ 已知差異（非錯誤）

| 檢查項 | 數量 | 說明 |
|--------|------|------|
| **孤立 attachments** | **1 筆** | `20260115/ISO圖` — 參考用資料夾，非修改單，無需處理 |
| **AG 圖片欄位命名差異** | **27 筆** | `_AG`/`_BG` 資料夾用 `before_1.jpg` / `before_2.jpg` 多圖命名，record 寫 `before.jpg=有` 代表「有照片」。**程式碼已正確處理**（`check_images_exist()` 有 fallback 邏輯），不影響功能 |

### 修復紀錄（2026-03-04）

| 項目 | 動作 | 結果 |
|------|------|------|
| 孤立 details (6 筆) | 從 details[] 移除紀錄編號找不到對應 record 的項目 | 729 → 723 |
| _ERROR.txt (6 筆) | 刪除 20250808、20250818、20250825 下的舊錯誤標記 | 全部清除 |
| Weld snapshot | 執行 `WeldSnapshotManager.build_snapshot()` 全量重建 | 161 → 171 folders, 671 welds |
| Product_report_.py | 加入棄用警告 + `__main__` 硬擋，防止誤執行 | 已封存 |
| AG 圖片欄位 (27 筆) | 確認為誤報 — `check_images_exist()` 已有 fallback | 無需修改 |

---

## 6. 風險評估

### 🔴 高風險

| # | 風險 | 影響範圍 | 說明 |
|---|------|----------|------|
| **H1** | ~~details 孤立紀錄~~ | ~~明細表匯出、GUI 明細顯示~~ | ✅ 已修復（2026-03-04 清除 6 筆孤立 details） |
| **H2** | 無即時一致性驗證 | records ↔ attachments | 刪除/歸檔 attachments 後，records.json 不會自動同步。任何讀取 records 後去 attachments 找檔案的功能都可能崩潰 |
| **H3** | ~~Product_report_.py 平行操作~~ | ~~舊 Excel 紀錄清單~~ | ✅ 已封存（2026-03-04 加入硬擋，直接執行會 exit(1)） |
| **H4** | JSON 無檔案鎖 | records.json | GUI + CLI 同時 upsert → 互相覆蓋。Google Drive 多台電腦同步更危險 |

### 🟡 中風險

| # | 風險 | 影響範圍 | 說明 |
|---|------|----------|------|
| **M1** | ~~AG 多圖命名 vs 記錄欄位不匹配~~ | ~~圖片明細功能~~ | ✅ 誤報 — `check_images_exist()` 已有 `before_1` fallback，欄位 `有` 代表「有照片」 |
| **M2** | ~~weld_snapshot 過時~~ | ~~焊口重複性檢查~~ | ✅ 已修復（2026-03-04 重建，171 folders / 671 welds） |
| **M3** | ~~6 筆 _ERROR.txt 殘留~~ | ~~重試機制~~ | ✅ 已修復（2026-03-04 刪除全部 6 筆） |
| **M4** | billing.json 無原子寫入 | 請款資料 | 直接 json.dump 到檔案，中斷時可能損壞（目前為空，暫無影響） |
| **M5** | settings.json 絕對路徑 | 跨機器相容 | 舊版曾把個人雲端路徑寫死在設定裡，換電腦帳號就失效 |
| **M6** | dwg_map.json 只有 5 筆 | DWG 對照 | 看起來非常少，可能快取沒正確建立或 DWG LIST 讀取有問題 |

### 🟢 低風險

| # | 風險 | 說明 |
|---|------|------|
| **L1** | 硬編碼 fallback 路徑 | 舊版曾在 config.py、debug_excel.py、Product_report_.py 保留個人雲端路徑 |
| **L2** | `records.json` 的 `materials` 區段 | gui_panels 嘗試讀但從未被寫入，永遠為空 |
| **L3** | pypdf / PyPDF2 雙 import | 兩套 PDF 庫同時安裝可能版本衝突 |
| **L4** | auto_backup 只保留 5 個 | 批次處理時可能不夠 |
| **L5** | Excel COM 殘留進程 | 異常終止時 atexit 可能未觸發 |

---

## 7. 延伸建議

### 🔧 立即可修（本次可做）

| # | 建議 | 說明 | 難度 |
|---|------|------|------|
| **F1** | ~~清理 details 孤立紀錄~~ | ✅ 完成（729 → 723） | — |
| **F2** | ~~清除舊 _ERROR.txt~~ | ✅ 完成（6 筆刪除） | — |
| **F3** | ~~修正 AG 的 before.jpg 欄位~~ | ✅ 確認為誤報，無需修改 | — |
| **F4** | ~~重建 weld_snapshot~~ | ✅ 完成（161→171 folders, 671 welds） | — |

### 🏗️ 架構改善（後續迭代）

| # | 建議 | 說明 | 優先級 |
|---|------|------|--------|
| **A1** | 新增 `audit_integrity()` 函數 | 將本次掃描邏輯嵌入系統，啟動時自動跑一致性檢查 | 高 |
| **A2** | records 刪除時聯動清理 details | `upsert_record` / 刪除時自動清理對應的 details | 高 |
| **A3** | AG 多圖命名標準化 | 統一圖片欄位支援 `before_N.jpg` 格式，或在 record 中改用清單 | 中 |
| **A4** | 加入 JSON Schema 驗證 | 對 records.json 的每筆寫入做 schema 驗證 | 中 |
| **A5** | ~~移除/封存 Product_report_.py~~ | ✅ 已加入棄用警告 + `__main__` 硬擋 | — |
| **A6** | 加入檔案鎖（filelock） | 防止 GUI + CLI 或多台電腦同時寫入 records.json | 高 |
| **A7** | settings 路徑改相對路徑 | 支援 `$PROJECT_ROOT` 變數或自動偵測 | 中 |
| **A8** | weld_snapshot 自動刷新 | 在 upsert_record 後自動更新 snapshot，而非手動 | 中 |
| **A9** | billing.json 改用原子寫入 | 仿照 records.json 的 `.tmp` + `os.replace()` 機制 | 低 |

### 🚀 上 GitHub 前的準備

| # | 項目 | 說明 |
|---|------|------|
| **G1** | `.gitignore` | 排除 `.venv/`, `__pycache__/`, `logs/`, `records/backups/`, `.weld_cache/`, `~$*.xlsm`, `*.tmp` |
| **G2** | 移除硬編碼路徑 | 清理所有個人雲端路徑 fallback |
| **G3** | 敏感資料檢查 | 確認 records.json, settings.json 不含敏感個資 |
| **G4** | ~~Product_report_.py 處置~~ | ✅ 已加 deprecation warning + exit guard |
| **G5** | 測試覆蓋率 | 目前 tests/ 有 4 個測試檔，需確認是否覆蓋核心邏輯 |

---

## 附錄：掃描腳本

完整性掃描腳本位於 `_audit_data.py`，可隨時重跑：

```bash
.venv\Scripts\python.exe _audit_data.py
```
