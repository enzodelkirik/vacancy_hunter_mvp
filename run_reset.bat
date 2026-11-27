@echo off
chcp 65001 >nul
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Виртуальное окружение .venv не найдено.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" main.py reset
echo.
echo Очистка завершена. Нажми любую клавишу для выхода...
pause >nul