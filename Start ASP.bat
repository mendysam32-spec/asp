@echo off
REM Start ASP dashboard if needed, then open browser
cd /d "C:\Users\kumen\AGENT SP"
powershell -NoProfile -Command "try { $null = Invoke-WebRequest -Uri 'http://localhost:5001/api/health' -TimeoutSec 3 -UseBasicParsing; exit 0 } catch { exit 1 }"
if errorlevel 1 (
  echo Starting ASP server...
  cscript //nologo scripts\start_hidden.vbs
  timeout /t 6 /nobreak >nul
)
start http://localhost:5001
