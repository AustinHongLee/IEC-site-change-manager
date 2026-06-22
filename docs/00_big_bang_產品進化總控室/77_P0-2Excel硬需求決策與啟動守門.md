# 77 P0-2 Excel 硬需求決策與啟動守門

日期：2026-06-22

## 決策

公司版工務修改單正式要求 Microsoft Excel。

沒有安裝 Excel、Excel 授權不可用、或 Excel COM 無法啟動的電腦，不允許使用此軟體。這不是 fallback 場景，也不是短期要支援的部署環境。

## 原因

- 公司使用者電腦可保證有 Excel。
- 現有核心修改單輸出依賴 `.xlsm` 樣板、Excel COM、VBA 巨集貼圖與 Excel SaveAs。
- 目前最高價值是把 Excel 依賴變成明確產品條件：啟動前擋、release 前驗、錯誤訊息講人話。
- 無 Excel renderer 屬於未來產品線選項，不是現在的 P0。

## 已落地

- 正常 GUI/CLI 啟動前先 probe Excel COM。
- Excel 不可用時 exit code 為 `4`。
- GUI 會跳出「此電腦不符合使用條件」訊息。
- CLI 會印出公司版硬需求說明，不再說「仍可使用非 COM 功能」。
- `--health-check`、`--audit-integrity`、`--diagnostics`、`--version` 仍可用，避免問題電腦無法產診斷資料。
- `build_release.py` 預設執行 packaged CLI 真輸出 smoke；如果只是快速驗假 package，需明確使用 `--no-cli-smoke`。

## 驗收標準

- 公司正式 release 必須在有 Excel 的機器上執行 `build_release.py`，並讓 packaged CLI smoke 產出至少一張 `.xlsm`。
- 沒有 Excel 的機器不可視為支援環境。
- 若未來要支援無 Excel，必須另開非 COM 修改單 renderer 專案，不可把它當作目前 EXE 產品化的阻塞項。
