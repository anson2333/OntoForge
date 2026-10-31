@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
if exist "backend\.venv\Scripts\python.exe" (
  "backend\.venv\Scripts\python.exe" "scripts\local_launcher.py" stop
) else (
  python "scripts\local_launcher.py" stop
)
if errorlevel 1 (
  pause
  exit /b 1
)
echo 已停止前后端；论文、接口配置与数据库均保留。
