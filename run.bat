@echo off
REM Ejecuta Quick Mechanic desde el codigo (sin compilar)
setlocal
cd /d "%~dp0"
python -m pip install -r requirements.txt
python -m quickmechanic %*
