@echo off
REM Double-click to run the app. Equivalent to:
REM   powershell -ExecutionPolicy Bypass -File .\run-app.ps1
REM Supports args passthrough, e.g.: run.bat -NoDocker
powershell -ExecutionPolicy Bypass -File "%~dp0run-app.ps1" %*
