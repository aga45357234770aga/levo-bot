@echo off
title KriptoLevo Otomatik Al-Sat Botu (Test Modu)
cd /d "C:\Users\Arif\.gemini\antigravity\scratch\kriptolevo-bot"
netstat -ano | findstr ":8501" | findstr "LISTENING" >nul
if %errorlevel% neq 0 (
    start /min "" pythonw "C:\Users\Arif\.gemini\antigravity\scratch\kriptolevo-bot\web_server.py"
    timeout /t 2 /nobreak >nul
)
start "" "http://localhost:8501"
