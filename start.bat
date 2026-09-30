@echo off
rem Double-click to start Job Radar and open it in your browser. Close this window to stop the app.
cd /d "%~dp0"
title Job Radar

rem If an older Job Radar is still running (e.g. from before an update), close it first so you get the latest version.
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -like '*run.py*ui*' } | ForEach-Object { Write-Host ('Closing the previous Job Radar (process ' + $_.ProcessId + ')...'); Stop-Process -Id $_.ProcessId -Force }"

if not exist ".venv\Scripts\python.exe" (
    echo First run: setting up...
    python -m venv .venv
)
rem Installs anything new that an update needs (quick when everything is already installed).
.venv\Scripts\python.exe -m pip install -q -r requirements.txt --disable-pip-version-check

rem Open the browser after a short delay so the server is ready.
start "" /b cmd /c "timeout /t 3 >nul & start http://127.0.0.1:5000"
.venv\Scripts\python.exe run.py ui
pause
