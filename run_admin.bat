@echo off
cd /d "%~dp0admin"
echo.
echo   YJ Atlas 管理后台
echo   ─────────────────
echo.
start "" http://localhost:5000
C:\Users\93166\AppData\Local\Programs\Python\Python314\python.exe app.py
pause
