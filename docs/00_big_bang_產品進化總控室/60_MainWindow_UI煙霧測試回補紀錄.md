# MainWindow UI 煙霧測試回補紀錄

日期：2026-06-22

## 背景

輸出中心後續可能從紀錄管理內的一顆按鈕，升級為更正式的交付中心或分頁。這類 UI 調整會碰到 `MainWindow` 與 `RecordManagerPanel` 的組裝關係，因此在動架構前需要一個主視窗層級的 smoke test。

## 本次新增

更新 `tests/test_output_center_ui_smoke.py`：

- 建立 `MainWindow`。
- 確認主要 tab 仍存在：
  - 產出報告
  - 紀錄管理
  - 材料價目
  - 請款追蹤
  - 設定
  - 健康
- 確認 `record_panel` 內仍可找到「輸出中心」入口。

## 邊界

本次只加測試，不改 UI 架構。測試不啟動 event loop、不執行輸出、不寫 records。

## 驗收

已執行：

```powershell
python -m pytest -s -q tests/test_output_center_ui_smoke.py
```

結果：

```text
3 passed
```

## 下一步

可以開始準備「輸出中心正式分頁」的小步設計：先抽出輸出中心入口/結果組裝的可測邏輯，再讓分頁與舊按鈕共用同一條 runner。
