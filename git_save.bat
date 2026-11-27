@echo off
chcp 65001 >nul
cd /d "%~dp0"
git status -s
set /p MSG="Комментарий к коммиту (Enter = update scoring): "
if "%MSG%"=="" set MSG=update scoring
git add -A
git commit -m "%MSG%"
git push
pause