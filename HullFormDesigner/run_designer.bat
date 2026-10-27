@echo off
rem Parametric Hull Form Designer (Windows): creates a virtual environment on first start.
cd /d "%~dp0"
if not exist .venv (
  py -3 -m venv .venv
  .venv\Scripts\pip install -r requirements.txt
)
.venv\Scripts\pythonw main.py %*
