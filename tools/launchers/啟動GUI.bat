@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul 2>&1
cd /d "%~dp0..\.."

:: ══════════════════════════════════════════════
:: 0. 讀取指定的 Python 版本 (.python-version)
:: ══════════════════════════════════════════════
set "REQUIRED_VER="
if exist ".python-version" (
    set /p REQUIRED_VER=<.python-version
)
if not defined REQUIRED_VER (
    echo [ERROR] 找不到 .python-version 檔案
    pause
    exit /b 1
)
echo [INFO] 專案要求 Python !REQUIRED_VER!

:: ══════════════════════════════════════════════
:: 1. 找到對應版本的系統 Python
:: ══════════════════════════════════════════════
set "SYS_PY="

:: 優先用 py launcher 指定版本（最可靠）
py -!REQUIRED_VER! --version >nul 2>&1
if !errorlevel! equ 0 (
    set "SYS_PY=py -!REQUIRED_VER!"
    goto :found_python
)

:: 其次用 PATH 上的 python，但驗證版本
python --version >nul 2>&1
if !errorlevel! equ 0 (
    for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do (
        for /f "tokens=1,2 delims=." %%a in ("%%v") do (
            if "%%a.%%b"=="!REQUIRED_VER!" (
                set "SYS_PY=python"
                goto :found_python
            ) else (
                echo [WARN] PATH 上的 Python 為 %%a.%%b，需要 !REQUIRED_VER!
            )
        )
    )
)

:: 最後搜尋常見安裝路徑（只找對應版本）
set "VER_NO_DOT=!REQUIRED_VER:.=!"
for %%P in (
    "%LOCALAPPDATA%\Programs\Python\Python!VER_NO_DOT!\python.exe"
    "C:\Python!VER_NO_DOT!\python.exe"
) do (
    if exist %%P (
        set "SYS_PY=%%~P"
        goto :found_python
    )
)

:: 完全找不到
echo.
echo ===================================
echo  [ERROR] 找不到 Python !REQUIRED_VER!
echo  請安裝: https://www.python.org/downloads/
echo  或修改 .python-version 檔案
echo ===================================
pause
exit /b 1

:found_python
echo [INFO] 系統 Python: !SYS_PY!

:: ══════════════════════════════════════════════
:: 2. 驗證 venv 是否正常 + 版本是否匹配
:: ══════════════════════════════════════════════
if exist ".venv\Scripts\python.exe" (
    :: 測試能否執行（Google Drive 佔位檔偵測）
    .venv\Scripts\python.exe --version >nul 2>&1
    if !errorlevel! neq 0 goto :rebuild_venv
    .venv\Scripts\python.exe -c "import sys" >nul 2>&1
    if !errorlevel! neq 0 goto :rebuild_venv

    :: 測試版本是否與 .python-version 一致
    for /f "tokens=2 delims= " %%v in ('.venv\Scripts\python.exe --version 2^>^&1') do (
        for /f "tokens=1,2 delims=." %%a in ("%%v") do set "VENV_VER=%%a.%%b"
    )
    if "!VENV_VER!" neq "!REQUIRED_VER!" (
        echo [WARN] venv 版本 !VENV_VER! 與要求 !REQUIRED_VER! 不符，重建中...
        goto :rebuild_venv
    )
    goto :check_deps
)

:: ══════════════════════════════════════════════
:: 2. 建立 / 重建 venv
:: ══════════════════════════════════════════════
:rebuild_venv
if exist ".venv" (
    echo [WARN] .venv 損壞或為雲端佔位檔，正在重建...
    rmdir /s /q .venv 2>nul
    :: Google Drive 可能在刪除後立刻恢復空殼，等待同步
    timeout /t 2 /nobreak >nul 2>&1
    if exist ".venv" (
        echo [WARN] Google Drive 殘留 .venv，嘗試清除中...
        rmdir /s /q .venv 2>nul
        timeout /t 2 /nobreak >nul 2>&1
    )
) else (
    echo [INFO] 找不到虛擬環境，正在建立 .venv ...
)

:: 嘗試用標準方式建立 venv
set "TEMP_VENV=%TEMP%\_venv_rebuild"
if exist "!TEMP_VENV!" rmdir /s /q "!TEMP_VENV!" 2>nul
!SYS_PY! -m venv .venv 2>nul
if !errorlevel! neq 0 (
    :: Google Drive 可能攔截 .exe 寫入，改用 TEMP 中轉
    echo [INFO] 偵測到雲端硬碟限制，使用中轉方式建立...
    !SYS_PY! -m venv "!TEMP_VENV!"
    if !errorlevel! neq 0 (
        echo [ERROR] 建立 venv 失敗
        pause
        exit /b 1
    )
    robocopy "!TEMP_VENV!" ".venv" /MIR /R:3 /W:1 /NFL /NDL /NJH /NJS >nul 2>&1
    :: robocopy 可能跳過 python.exe，用 rename 技巧補救
    if not exist ".venv\Scripts\python.exe" (
        copy "!TEMP_VENV!\Scripts\python.exe" ".venv\Scripts\python.dat" >nul 2>&1
        ren ".venv\Scripts\python.dat" python.exe >nul 2>&1
    )
    rmdir /s /q "!TEMP_VENV!" 2>nul
)
if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] 無法建立 .venv\Scripts\python.exe（雲端硬碟可能鎖定了該檔案）
    echo 建議：暫時將專案複製到本機磁碟後執行，或暫停 Google Drive 同步。
    pause
    exit /b 1
)
.venv\Scripts\python.exe -m ensurepip --upgrade >nul 2>&1
if !errorlevel! neq 0 (
    echo [ERROR] 安裝 pip 失敗
    pause
    exit /b 1
)
echo [INFO] 虛擬環境建立完成，安裝依賴...
.venv\Scripts\python.exe -m pip install -r requirements.txt
if !errorlevel! neq 0 (
    echo.
    echo ===================================
    echo  依賴安裝失敗，請手動執行：
    echo  .venv\Scripts\python.exe -m pip install -r requirements.txt
    echo ===================================
    pause
    exit /b 1
)
echo [INFO] venv 重建完成
goto :launch

:: ══════════════════════════════════════════════
:: 3. 檢查依賴是否完整
:: ══════════════════════════════════════════════
:check_deps
.venv\Scripts\python.exe -c "import openpyxl, pypdf, fitz, PIL, PyQt6, win32com.client" >nul 2>&1
if !errorlevel! neq 0 (
    echo [INFO] 偵測到缺少套件，正在自動安裝依賴...
    .venv\Scripts\python.exe -m pip install -r requirements.txt
    if !errorlevel! neq 0 (
        echo.
        echo ===================================
        echo  依賴安裝失敗，請手動執行：
        echo  .venv\Scripts\python.exe -m pip install -r requirements.txt
        echo ===================================
        pause
        exit /b 1
    )
    echo [INFO] 依賴安裝完成
)

:: ══════════════════════════════════════════════
:: 4. 啟動 GUI
:: ══════════════════════════════════════════════
:launch
cd /d "%~dp0control"
set PYTHONIOENCODING=utf-8
"%~dp0.venv\Scripts\python.exe" main.py

if !errorlevel! neq 0 (
    echo.
    echo ===================================
    echo  啟動失敗，錯誤碼: !errorlevel!
    echo ===================================
    echo.
    pause
)
