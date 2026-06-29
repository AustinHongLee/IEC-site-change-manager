@echo off
set "PAGE=%~dp0control\co_main_web\index.html"

if not exist "%PAGE%" (
  echo Cannot find: "%PAGE%"
  echo This .bat must sit in the project root folder.
  pause
  exit /b 1
)

start "" "%PAGE%"
