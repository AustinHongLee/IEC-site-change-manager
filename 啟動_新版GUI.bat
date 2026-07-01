@echo off
cd /d "%~dp0"
title CO Manager - New GUI (Desktop)

rem Launch the native desktop window (pywebview)
python control\co_main_app.py
if errorlevel 1 (
  echo.
  echo [Launch failed] See the message above.
  echo  - Missing pywebview?   run:  pip install pywebview
  echo  - Missing WebView2 Runtime? download "Evergreen WebView2 Runtime" from Microsoft
  echo.
  pause
)
