@echo off
setlocal
set "PYTHON=python"
if exist ".venv\Scripts\python.exe" set "PYTHON=.venv\Scripts\python.exe"
%PYTHON% -m PyInstaller --noconfirm --windowed --name DiskBloom --add-data "assets;assets" main.py
if errorlevel 1 exit /b %errorlevel%
echo Build complete. See dist\DiskBloom.
