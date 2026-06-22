# P0 Repo 護欄回補紀錄

日期：2026-06-22

## 背景

Opus 在 `53_下一步計畫書_輸出中心閉環與EXE產品化.md` 指出一個 P0 風險：在多 AI、多人、Windows 編輯器混用的情境下，repo 很容易出現整檔行尾翻動、巨大 diff、或核心程式修改沒有測試保護。

本回補不處理產品功能，也不改 UI。目的只是在繼續做輸出中心、EXE 產品化之前，先建立最低限度的機械護欄。

## 本次新增

- `.editorconfig`
  - 鎖 UTF-8、LF、Python 4 spaces。
  - Windows 腳本 `.bat/.cmd/.ps1` 保留 CRLF。
- `.githooks/pre-commit`
  - 呼叫 `python tools/repo_guard.py --staged`。
- `tools/repo_guard.py`
  - 跑 staged 或 working tree 的 `git diff --check`。
  - 擋過大的單次變更。
  - 擋疑似行尾或整檔重存造成的 balanced rewrite。
  - 擋 `control/*.py` 有改，但沒有 `tests/*.py` 變更。
- `tools/install_git_hooks.py`
  - 將本機 `core.hooksPath` 指向 `.githooks`。
- `tests/test_repo_guard_tool.py`
  - 驗證 numstat parser、過大 diff、balanced rewrite、control/test 配對規則。

## 使用方式

開發者或 AI agent 在本機啟用 hook：

```powershell
python tools/install_git_hooks.py
```

手動檢查 staged changes：

```powershell
python tools/repo_guard.py --staged
```

手動檢查 working tree：

```powershell
python tools/repo_guard.py
```

若某次變更確實需要超過門檻，應明確提高參數並在 commit 或回補紀錄中說明原因，不應靜默繞過。

## 驗收

已執行：

```powershell
python -m pytest -q tests/test_repo_guard_tool.py
```

結果：

```text
6 passed
```

## 下一步

P0 護欄還缺兩件事：

1. 加一個更完整的 UI smoke test，保護後續「輸出中心升成正式分頁」。
2. 讓每次 AI 工作結束時自動留下 `git diff --stat`、測試結果、health-check 摘要，形成可追蹤的 AI session 紀錄。
