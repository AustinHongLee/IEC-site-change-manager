# Opus 校準結果 — Checkpoint C（xlsx template renderer / 渲染管線第一版）

對應：前導書 `09_現場資料核心與多格式輸出前導書.md` 的 Phase 0 + Phase 1。
審查日期：2026-06-16
審查方式：直接讀渲染管線原始碼，並在隔離沙箱實跑「欄位閘門 / 三原語 / COM 隔離 / 表格溢出」。

審查模組：`canonical_report.py`、`canonical_fields.py`、`template_mapping.py`、
`template_dry_run.py`、`xlsx_template_renderer.py`，及工具 `validate_template.py`、
`list_canonical_fields.py`、`render_xlsx_template.py`。

---

## 0. 先講結論

Codex 沒有跳過 Phase 0。前導書的核心契約——**CanonicalReport + 封閉 field-path 目錄 + 三原語 + 驗證閘門 + COM 移出核心**——
五個都真的落地了，而且實測成立。**可以收下這一版。**
但有一個 🔴 必修：**表格溢出只「偵測」沒「執行」**，會靜默蓋掉表格下方的儲存格（已用沙箱重現）。修掉它，Phase 1 才算驗收通過。

---

## 1. 已驗證成立（實跑確認）

- **欄位閘門是真的**：`validate_template_mapping` 把每個 `source` 對 `canonical_fields` 目錄比對；text/image 不准用 `[*]`/`[0..n]`；table 來源必須是清單路徑、欄位驗成 `source[*].col`。**引用不存在的路徑 → ERROR**。「AI 只新增模板、不改核心」的契約成立。
- **閘門擋在渲染前**：renderer 先跑 `dry_run`（內含 validate），不過就 `ok:False` 不寫檔。
- **COM 已移出核心**：全 `control/` 只有 `excel_handler.py` import `win32com`；canonical/mapping/dry_run/renderer 全程 openpyxl，無 COM。符合前導書 §4.4。
- **CanonicalReport 是真核心層**：`canonical_report.py` 收斂 records.json + attachments（焊口/材料/照片/note/附件/指紋），算 aggregates 與 issues，並把 `field_paths` 目錄一起塞進 report set。renderer 吃的是這份模型，不是生資料。Phase 0 成立。
- **三原語**：text / image / table，與前導書一致。
- **圖片優雅降級**：缺路徑→寫「缺圖片」、檔案不存在→「找不到圖片」、讀不了→「無法讀取圖片」，都給 warning 不崩。等比縮放有做（預設 260×180px）。
- **原子寫檔**：`_atomic_save_workbook` 走 .tmp + os.replace。
- **dry-run 會報缺漏**：文字無值、圖片無路徑/檔案不存在都列 warning（前導書 UI 第 6 步「哪些資料沒填入」的雛形）。

沙箱實測：欄位閘門擋下未知路徑、合法模板 `validate ok`、圖片/文字/表格三原語都正確寫入。

---

## 2. 缺口（依嚴重度）

### 🔴 C1. 表格溢出「偵測到卻照寫」，會蓋掉下方儲存格（已重現）
`dry_run` 會在 `max_rows`/`rows_per_page` 設定時算出 `overflow_count` 並發 `table_overflow` **warning**；
但 `xlsx_template_renderer._render_table` **完全沒讀 `max_rows`**，無條件把所有列從 `start_cell` 往下寫。

沙箱重現（max_rows=2、實際 4 列、footer 放在預留區下方）：
```
dry-run issues: table_overflow - 表格資料 4 列超過預留 2 列，超出 2 列
render ok: True   rows written: 4
A3='C1'  A4='C2'  A5='C3'  A6=（第4列/footer 互相覆蓋）
```
即：**警告有了，檔案照樣把資料寫進 A5/A6，撞掉表格下方的版面**。而且：

- `max_rows` 是**選填**。作者沒設 → `overflow_count=0` → **連警告都沒有**，無限往下寫，更危險。
- 這正是前導書 §8 點名要擋的「材料列超出表格區」與「寧可大聲報、絕不安靜地漏」。現在是「小聲報、照樣漏」。

**修法（擇一，建議 a+c）**：
a) renderer 讀 `max_rows`，**超出就截斷並把 `table_overflow` 升成 render-level ERROR**（`ok:False` 或明確標記），不要靜默寫過界；
b) 真正分頁（new_sheet / 續區塊）——前導書原訂目標，可留到 Phase 2；
c) **table 一律要求 `max_rows`**（mapping 驗證時缺 `max_rows` 就擋），讓「沒保護」這個狀態不可能存在。

### 🟠 C2. 沒有「輸出後校驗」（ValidationReporter 後半段）
renderer 把 dry-run 的 issues 併進結果，但**沒有產出後再回讀檔案確認真的放進去**。
前導書 §5/§8 的「輸出後校驗報告」目前只到 dry-run 前測，缺 after 測。v1 可接受，但請列入待辦。

### 🟠 C3. 沒有反向「孤兒資料」報告
dry-run 是 模板欄位→值 方向（哪些欄位沒值）。缺**反向**：CanonicalReport 有資料、但沒有任何模板欄位用到它（前導書 UI 第 6 步「哪些資料沒填入模板」的完整版）。對「現場統計單怕漏資料」這點有用，建議補。

### 🟡 C4. 圖片以 anchor + 像素尺寸落點，無重疊/越界偵測
兩張圖或圖與表格區可能重疊，目前不檢查。第一版可接受，記一筆。

### 🟡 C5. 舊 COM 輸出路徑仍在，未降級
新 renderer 是**平行新路徑**；舊 `excel_handler.py`（COM）還在。前導書 Phase 0 設想是「既有輸出改走 CanonicalReport」，目前是「另開新路」。不是錯，但代表現在有兩條輸出路。COM 路徑的降級/隔離要排進後續。

### 🟡 C6. 目錄小冗餘
`canonical_fields` 同時有 `photos.before[0..n]` 與 `photos.before[*].path` 兩種寫法，易混淆。建議統一以 `[*]` 為正，`[0..n]` 留給文件說明即可。

---

## 3. 對照前導書 Phase 0 / Phase 1 驗收

- **Phase 0（資料核心歸一）**：✅ 大致達成。CanonicalReport(Set) + 完整度 + field-path 目錄 + `list-fields` 工具都有。
  待辦：把既有輸出也接上 canonical（C5）。
- **Phase 1（mapping + openpyxl renderer + dry-run）**：🟡 約 8 成。三原語、閘門、dry-run、貼圖、CLI、247 測試都有；
  **卡在 C1**：dry-run 能預告溢出，但 renderer 不照辦。補上溢出執行，Phase 1 才算收。
  另建議補第 2 份不同公司模板，真正驗證「零核心改動換格式」（目前 smoke 只有 1 份）。

---

## 4. 下一步建議

1. **先修 C1（必修）**：renderer 讀 `max_rows` → 截斷 + 升 ERROR；table 驗證強制要 `max_rows`。修完 Phase 1 收尾。
2. 補第 2 份公司模板 + 一個「孤兒資料」報告（C3），把「換格式不改核心」與「不漏資料」兩個賣點坐實。
3. 進 Phase 2（PDF overlay + LibreOffice 轉檔）前，先把 C2 輸出後校驗補上——PDF 的溢出/座標風險比 Excel 高，沒有 after 測會痛。
4. C5（COM 降級）排進 Phase 2/3，與 PDF 路線一起收。

---

## 5. 一句話

契約落地紮實、方向完全正確，COM 也乾淨切開了。唯一擋驗收的是 C1——**把「偵測到溢出」變成「真的不讓它蓋過界」**，這版就穩了。
