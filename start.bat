@echo off
title Multi-Telegram Tool v8
color 0A
echo.
echo  ============================================
echo    Multi-Telegram Tool v8 - Web Interface
echo  ============================================
echo.
echo  Kiem tra Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo  [LOI] Python chua duoc cai dat!
    echo  Tai Python tai: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo  Kiem tra dependencies...
python -c "import fastapi" >nul 2>&1
if errorlevel 1 (
    echo  Dang cai dependencies...
    pip install fastapi uvicorn[standard] telethon opentele pygetwindow pywin32 2>&1
    if errorlevel 1 (
        echo  [CANH BAO] Mot so package co the chua cai duoc, thu tiep...
    )
)

echo  Khoi dong server tai http://localhost:8899
echo  Trinh duyet se tu dong mo sau 2 giay...
echo  Nhan Ctrl+C de thoat
echo.
python app.py
pause
