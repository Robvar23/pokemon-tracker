@echo off
rem Pokemon Tracker for Windows. Double-click to start. Add  --test  to send a test message.
cd /d "%~dp0"
set "PY=python"
where python >nul 2>nul && python -c "import sys" >nul 2>nul && goto havepy
set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if exist "%PY%" goto havepy

echo Python is not installed yet - installing it for you (one time only)...
winget install -e --id Python.Python.3.12 --scope user --silent --accept-package-agreements --accept-source-agreements
if not exist "%PY%" (
  echo.
  echo Automatic install didn't work. Please install Python from https://www.python.org/downloads/
  echo ^(tick "Add Python to PATH"^), then double-click run.bat again.
  pause
  exit /b 1
)

:havepy
if not exist .venv (
  echo First run: setting things up, this takes a minute...
  "%PY%" -m venv .venv || (pause & exit /b 1)
  .venv\Scripts\python -m pip install --upgrade pip
  .venv\Scripts\python -m pip install -r requirements.txt || (pause & exit /b 1)
)
.venv\Scripts\python main.py %*
pause
