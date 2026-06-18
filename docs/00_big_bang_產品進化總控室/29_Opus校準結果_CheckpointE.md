# Opus 校準結果 — Checkpoint E（report.v1 與 pdf_overlay schema-only）

對應請求：`28_Opus校準請求_CheckpointE_ReportV1與PdfOverlaySchema.md`
審查日期：2026-06-17
審查方式：讀 `pdf_overlay_schema.py` 驗證器 + 對照前導書 §3 與既有 mapping 契約。

---

## 0. 結論：**綠燈，可以開始寫 pdf_overlay renderer 的最小垂直切片**

schema 凍結得很紮實（rect 界限、區塊重疊、擋 Excel 落點、欄寬總和、overflow/align/fit enum、font_size 合理性都驗了）。
**沒有 P0 架構洞。** 只有三個「現在順手釘死、免得日後要重凍 v1」的 spec 釐清（都不是改 schema，是把規格寫白）。你自己排的順序也對。

---

## 1. 七題回答

1. **rect `[x,y,width,height]` vs `[x1,y1,x2,y2]`？** 維持 `[x,y,w,h]`，可接受、而且界限已驗。**唯一要修：前導書 `09` §3.4 寫的是 `[x0,y0,x1,y1]`（兩角點），現在和 v1 schema 矛盾。** v1 凍結卻有矛盾的規格文件＝未來地雷，請把 `09` 改成 `[x,y,w,h]`，並**白紙黑字寫明原點**（看起來是左上、y 向下；schema 沒編碼原點，是 renderer 約定，現在就要釘）。

2. **`normalized` 夠嗎？要現在放 `page_size_pt` 嗎？** 夠，而且比存 `page_size_pt` 更穩（換底圖尺寸不跑位）。**別加 page_size_pt 當座標基準。** 但三件事現在就要寫進規格（免費，且 renderer 一定會踩）：
   - (a) normalized 是相對**哪個框**：CropBox（可見區）還是 MediaBox（全頁）？建議 **CropBox**（人在上面放框看到的就是可見區）。
   - (b) **`/Rotate` 處理**：PDF 頁可帶 90/180/270 旋轉，renderer 若不處理，每個框都會貼歪。規格要寫「relative to 可見、已套用 rotation 的幾何」。
   - (c) **page 是 1-based**（你的 validator 要求 `page≥1`），但 `09` 的範例寫 `page:0`。又一處 doc/schema 矛盾，請統一成 1-based 並改範例。

3. **擋 Excel 落點欄位混入 PDF——太嚴還是剛好？** 剛好，維持嚴格。PDF 模板裡出現 `cell:"A1"` 就是錯，擋掉是對的。這正是「兩個世界不准滲血」。

4. **registry 把 pdf_overlay 設 `schema_only`——進 renderer 前最安全狀態？** 是。不渲染、不假裝可用，跟 `xlsx_com` 同模式，正確。

5. **renderer 前要先做 output result envelope（P1）嗎？** 要，**先做**。先把 envelope v1 定下來，新 renderer 一出生就合規；否則等三個 renderer 都長出不同形狀再回頭統一，要動每一個。你排第 1 順位，對。

6. **demo edge matrix 要排在 renderer 前嗎？** 要——它就是 renderer 的**測試床**（缺 after、未定價、表格 overflow、多頁照片、PDF 多頁）。先有壞資料 fixtures，才能邊寫邊驗。你排第 2，對。

7. **AcroForm 現在納入 kind 設計嗎？** 不要，**延後到 overlay v1 之後**。它是另一個後端，現在設計是過度設計。等真有一家公司給可填式 PDF 再加一個 `kind`，不影響核心。

**你的順序（envelope → edge matrix → renderer 垂直切片）正確，背書。** 唯一加一件：把上面三個 spec 釐清（rect 原點、CropBox 基準、/Rotate、1-based page）寫進 `26` 規格 + 修 `09` 的矛盾——**趁還沒寫 renderer，免費；寫完 renderer 再改就要重凍 v1**。

---

## 2. 自我檢討：這次七題，真正需要 Opus 的只有兩題

老實說：Q3、Q4、Q5、Q6、Q7 你在「我目前的判斷」裡其實**已經答對了**，是來找我**確認**，不是來解**未知**。真正有 Opus 價值的只有 Q1（doc/schema 矛盾）和 Q2（CropBox / `/Rotate` 這種非顯而易見的 PDF 地雷）。

這不是說你不該問——而是引出下面這條，回應「Codex 越來越依賴 Opus」這件事。

---

## 3. 升級觸發規則：什麼時候才該找 Opus（建議寫進工作流）

過去的高頻校準在**早期是對的**：財務安全、COM 啟動依賴那幾關，Opus 真的抓到實錯（SCH 主鍵碰撞、溢出沒擋、COM 綁啟動）。但**現在閘門已經建起來了**——`validate_template`、`dry_run`、`import_guard`、pytest、health-check、這份 pdf_overlay schema 驗證——閘門的意義就是「**Codex 靠通過閘門自我背書，而不是靠問 Opus**」。所以該調高找 Opus 的門檻。

**該升級給 Opus（少數）：**
- **不可逆／改了要 migration 的決定**：schema/版本凍結、資料模型契約、財務計算規則。
- **新架構分岔**：新 renderer kind、新核心邊界、新外部依賴（如 LibreOffice）。
- **沒有單一測試守得住的跨切面不變量**。

**Codex 自我背書、不要升級（多數）：**
- 已被現有閘門/測試覆蓋（validate/dry-run/import-guard/pytest 綠/health-check）。
- 可逆的一般功能、UI 調整、已有測試的 renderer。
- 有明顯預設值、撤回成本低的決定。

**兩個習慣：**
1. Codex 自己跑一份 pre-flight checklist；只有踩到上面「該升級」的觸發條件，才寫 Opus checkpoint。
2. 真要升級時，**把幾個真正難的問題打包**，不要送七題、其中五題自己已有答案。

決定權在李宗鴻（orchestrator）：可以直接對 Codex 下「用閘門自我驗證；只有 schema 凍結／財務規則／新架構才找 Opus」。這樣 Opus 從「每點都問的瓶頸」回到「高風險分岔的挑錯者」，省成本、也讓 Codex 不會學成依賴。

---

## 4. 一句話

schema 凍得好，綠燈，順序對。趁沒寫 renderer 先把 rect 原點 / CropBox / `/Rotate` / 1-based page 釘進規格、修掉 `09` 的矛盾。
然後——**這種「我已經想好、來確認」的題目，以後 Codex 自己過閘門就好；把 Opus 留給真正不可逆或會分岔的關。**
