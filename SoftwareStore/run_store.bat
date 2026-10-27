@echo off
rem Software Store (Windows): double-click to start the web shop.
rem First start creates a virtual environment (.venv) and installs the requirements.
setlocal
cd /d "%~dp0"

if exist .venv\installed.ok goto run

set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY where python >nul 2>nul && set "PY=python"
if not defined PY (
  echo Python 3.10 or newer is required. Install it from https://www.python.org/downloads/
  echo and tick "Add python.exe to PATH" during installation.
  pause
  exit /b 1
)
echo Creating virtual environment...
if not exist .venv\Scripts\python.exe %PY% -m venv .venv || goto fail
.venv\Scripts\python -m pip install --upgrade pip >nul
.venv\Scripts\python -m pip install -r requirements.txt || goto fail
echo ok> .venv\installed.ok

:run
if not exist store.env copy /y store.env.example store.env >nul
.venv\Scripts\python serve.py
if errorlevel 1 goto fail
exit /b 0

:fail
echo.
echo Software Store stopped with an error. See the messages above.
pause
exit /b 1
