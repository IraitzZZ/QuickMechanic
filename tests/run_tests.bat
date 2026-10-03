@echo off
REM Lanza todos los tests (incluye los que leen la instalacion real de AC)
setlocal
cd /d "%~dp0"
python -m unittest discover -s tests -v
pause
