@echo off
chcp 65001 >nul
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Создание виртуального окружения .venv...
    python -m venv .venv
    if errorlevel 1 (
        echo Ошибка создания .venv. Проверь, что python установлен и добавлен в PATH.
        pause
        exit /b 1
    )
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    ".venv\Scripts\pip.exe" install -r requirements.txt
)

".venv\Scripts\python.exe" main.py search
echo.
echo Готово. Нажми любую клавишу для выхода...
pause >nul