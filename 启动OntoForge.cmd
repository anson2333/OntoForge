@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
echo 正在启动 OntoForge，请稍候...
if exist "backend\.venv\Scripts\python.exe" (
  "backend\.venv\Scripts\python.exe" "scripts\local_launcher.py" start
) else (
  python "scripts\local_launcher.py" start
)
if errorlevel 1 (
  echo.
  echo 启动未完成，请查看上方提示。首次运行需要安装 Python 3.11 和 Node.js。
  pause
  exit /b 1
)
echo 已就绪，浏览器已打开。此窗口将自动关闭。
