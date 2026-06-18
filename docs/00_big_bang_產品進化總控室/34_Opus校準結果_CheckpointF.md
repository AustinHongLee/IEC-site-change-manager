# Opus 校準結果 — Checkpoint F（pdf_overlay minimal renderer）

對應請求：`33_Opus校準請求_CheckpointF_PdfOverlayRenderer.md`
審查日期：2026-06-17
審查範圍：只看 `pdf_overlay` renderer 從 schema-only → minimal 的契約邊界（不重開材料/請款/整體路線）。
審查方式：讀 `pdf_overlay_renderer.py`，並在沙箱實跑重現一個 P0。

---

## 1. 總評：**可以繼續做 `overflow=new_page` 與多頁照片**，但先修一個 P0

renderer 的骨架做對了，而且把前面的教訓帶過來了：

- 走 dry-run 閘門 → 載 base → 頁碼範圍檢查 → 逐頁 rotation+overlay → 原子寫檔 → pypdf 回讀。
- **COM-free**（pypdf + reportlab）。
- **座標轉換正確**：以 CropBox 可見區為基準、top-left/y-down → PDF 左下，`_rect_to_points` 邏輯對。
- **`/Rotate` 處理對**：`transfer_rotation_to_content()` 後才讀 geometry、才 overlay，且**不動 base 原檔**（寫新輸出）。
- **table 溢出有擋**：超 `rows_per_page` → 丟 **error** → overlay ok=False → 不寫檔。C1 的教訓有繼承。
- image 有 clipPath，不會溢出框；缺圖/檔不存在/讀不了都優雅降級畫 placeholder。

**但有一個同類型的洞還沒補：`text` 的 `overflow=error` 會靜默截斷。** 因為你接下來要做的 `new_page` 本質也是「溢出處理」，**先把這個原則立正確，new_page 才不會複製同一個洞**。所以建議：修完 P0 再開 new_page。

---

## 2. P0 必修（會造成錯檔／資料不可追溯／公司表單不可信）

### P0-1　`text` 的 `overflow=error` 靜默截斷，且照樣產出 PDF（已沙箱重現）
`_render_text`（行 207-211）：不管哪種 overflow，先 `lines = lines[:max_lines]` 截斷；但**只有** `clip/shrink/wrap` 會 `_ellipsize` 加省略號，`error` 既不加標記、**也不發任何 issue**。後果：

- `overflow` 的 schema **預設值就是 `error`**（mapping 沒寫時 renderer 預設 error、dry-run 也說「將預設 error」）。
- 所以大量模板會落在 `error`，而 `error` 模式遇到放不下的文字 → **無聲截掉、無 error、PDF 照出**。

沙箱重現（小框 + 超長 description + `overflow:"error"`）：
```
render ok: True   issues: []   PDF produced: True
→ overflow=error 卻沒有任何 overflow error，照樣產出 PDF
```
這是公司表單上的**靜默資料遺失**（修改原因被默默砍半，沒人知道），正是 C1「寧可大聲報、絕不安靜漏」要擋的。

**修法**：`overflow=error` 遇到放不下 → 發 render-level `text_overflow` **error**，並讓該頁 ok=False（不要產出會誤導的 PDF）。其餘模式（clip/shrink/wrap）維持截斷但**一定要留標記**（省略號或 issue）。一句話：**沒有任何模式可以「無聲丟字又出檔」。**

---

## 3. P1 建議（GUI 前補，但不擋 renderer 下一步）

- **P1-1　schema 收了 `overflow=new_page/truncate`，但 renderer 一律當 error**（fail-safe，沒出壞檔，這點好）。問題是「**驗證說可以、renderer 不支援**」的契約落差——而且 `09` §3.5 範例與 demo 模板就寫 `new_page`。在真正實作前，renderer 應對未實作模式發**明確** `overflow_mode_unsupported`（不要用泛用 table_overflow 混淆），或 registry capability 標明「目前 overflow 僅支援 error」。讓作者不會以為會續頁、結果拿到 error。
- **P1-2　CJK 字型未嵌入**：用 `STSong-Light`（標準 CID 字型，非嵌入），Poppler 已提醒被換成 SimSun。送到客戶/別台機器可能變字或豆腐。**正式公司 PDF 前**要註冊並**嵌入** TTF（如 NotoSansTC）。這條在「對外交付」時會升級成 P0。
- **P1-3　輸出後驗證只到 pages>0**（沿用）：minimal 可接受；真實檢查靠 dry-run issues + 溢出 error 擋。
- **P1-4　非零 mediabox 原點的 base PDF** 可能讓 overlay 位移（overlay canvas 用 media 尺寸、rect 帶 crop 偏移；mediabox 不從 (0,0) 起的罕見 PDF 會偏）。少見，記一筆、加一個 fixture 測。
- **P1-5　envelope（Q8）**：`output_result.v1` 已夠 UI/CLI/AI 接管。建議再加：每個 issue 一個 `retryable` 旗標（區分 LibreOffice timeout 這種可重試 vs schema invalid 這種不可重試）＋ 頂層 severity 計數（`warnings_count`/`errors_count`，UI 做 badge 方便）。`artifacts` 先不用，`outputs` 已涵蓋。

---

## 4. 針對你問題的直接回答（Q2/Q3/Q4/Q5/Q6/Q7）

- **Q2 `/Rotate`**：做法安全，因為**你寫的是新輸出 PDF、base 原檔沒被改**。`transfer_rotation_to_content` 對純靜態底圖 OK。唯一保留意見：若 vendor 表單帶**註解/表單欄位**，旋轉轉內容在某些 pypdf 版本會有狀況——對這類底圖加一個 fixture 測即可，不必另建副本策略。
- **Q3 CropBox 基準**：正確且足夠。CropBox 是可見區（人在上面放框看到的就是它），無 CropBox 退 MediaBox（pypdf 預設行為一致）。**不要**加 ArtBox/TrimBox/BleedBox 優先序——那是印刷出血用，表單 overlay 用不到，加了只是增加誤用面。
- **Q4 `overflow=new_page` 怎麼做不破壞三原語**：
  - table **預設仍 error**，只有明確 `new_page` 才續頁（保住「不靜默溢出」）。
  - 續頁**預設複製同一張 base page**（表單頁首頁尾跟著重複），另給可選 `continuation_page`（1-based）讓有專屬續頁的表單指定。
  - `rows_per_page` 為**分頁列數的權威**；`rect` 高度 + `row_height` 決定畫法。兩者衝突（rows_per_page 列在該 rect 高度下放不下）→ **dry-run/驗證就報 error**，不要讓它畫爆 rect。
  - **dry-run 要能預測總頁數**，post-validate 對齊；別讓 new_page 變成 renderer 私密行為。
- **Q5 多頁照片 grid**：是 **`table` 的 grid 變體（cell 畫 image）**，不是新原語、也不是 image 的擴充。重用 `rows_per_page`/`new_page`。**維持三原語**。
- **Q6 AcroForm**：registry **另開 `kind`（如 `pdf_acroform`）**，不要塞進 pdf_overlay（填命名欄位 vs 座標貼字是兩種機制）。共用 field-path 目錄與 envelope，但自己的 target schema（欄名映射、無 rect_norm）。**現在先別做**（Checkpoint E 已定：overlay v1 之後）。
- **Q7 GUI 暴露前的 P0 防呆**：① 修 P0-1（不可無聲丟字）；② CJK 字型嵌入（P1-2，對外就升 P0）；③ render ok=False 時**不可把 PDF 當成功打開**（比照 xlsx 的「保留+提示」，但失敗就只給人話錯誤、不端出誤導 PDF）；④ capability 檢查 reportlab/pypdf，缺就灰掉選項（比照 LibreOffice）。

---

## 5. 下一步 3 件事（排序）

1. **修 P0-1**（text overflow=error 不可無聲丟字）＋ 把 table 的 `new_page/truncate` 未支援講清楚（P1-1）。先把「任何模式都不准無聲溢出」這條原則在 minimal 補滿，再往下。
2. **做 `overflow=new_page`**，照 Q4 的契約：預設仍 error、明確才續頁、預設複製 base page、`rows_per_page` 權威且 dry-run 預測頁數、放不下就 validation error。
3. **多頁照片 grid 當 `table` 的 grid 變體**（cell 畫 image，重用 new_page）；同時把 **CJK 字型嵌入**（P1-2）排在 GUI 暴露 pdf_overlay 之前。

---

## 6. 不要做的事（現在做會過度設計或打壞主線）

- 不要為 `new_page`／照片 grid 新增第 4 種原語——它們都是 `table`。
- 不要把 AcroForm 併進 pdf_overlay——另開 `kind`，且現在先不做。
- 不要做像素級視覺 diff 驗證——minimal 用「pages>0 + dry-run issues + 溢出 error」就好。
- 不要動 base PDF 原檔——維持「讀 base、寫新輸出」。
- 不要加 ArtBox/TrimBox/BleedBox 盒優先序——CropBox→MediaBox 已足。

---

## 7. 一句話

骨架穩、座標與 `/Rotate` 對、table 溢出有擋，可以往 `new_page` 與多頁照片走。
**唯一先擋你的是 P0-1：`text overflow=error` 會無聲丟字又出檔**——這跟你下一步要做的溢出處理是同一條原則，先補正，再開 new_page。
