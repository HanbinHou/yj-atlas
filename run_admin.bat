@echo off
cd /d "%~dp0admin"
start "" http://localhost:5000
C:\Users\93166\AppData\Local\Programs\Python\Python314\python.exe app.py
pause
