@echo off
setlocal

if not exist ".venv" (
    echo [ERROR] Virtual environment not found. Please run install.bat first.
    pause
    exit /b 1
)

call .venv\Scripts\activate
python main.py
if %errorlevel% neq 0 (
    echo [ERROR] Application exited with error.
    pause
)
