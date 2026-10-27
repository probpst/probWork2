@echo off
rem Builds the Windows program folder dist\HullFormDesigner\HullFormDesigner.exe (and a zip of it).
rem Needs: 64-bit Python 3.10 - 3.13 from python.org (py launcher). Run from this folder by double-click.
setlocal
cd /d "%~dp0"
if not exist .venv-build (
  py -3 -m venv .venv-build || goto :error
)
call .venv-build\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt pyinstaller || goto :error
python -m pytest -q tests -k "not cad_export" || echo WARNING: tests failed, building anyway
pyinstaller --noconfirm --clean packaging\HullFormDesigner.spec || goto :error
powershell -NoProfile -Command "Compress-Archive -Force -Path dist\HullFormDesigner -DestinationPath dist\HullFormDesigner-portable.zip"
echo.
echo Done: dist\HullFormDesigner\HullFormDesigner.exe
echo       dist\HullFormDesigner-portable.zip
echo Optional installer: open packaging\installer.iss in Inno Setup and press Compile.
goto :eof
:error
echo Build failed.
exit /b 1
