@echo off
REM Genera dist\Setup.exe; requiere Inno Setup 6 y QuickMechanic.exe ya compilado.
setlocal
cd /d "%~dp0"

if not exist "dist\QuickMechanic.exe" (
    echo No existe dist\QuickMechanic.exe. Ejecuta build_exe.bat primero.
    exit /b 1
)

set "ISCC="
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not defined ISCC (
    echo No se encontro Inno Setup 6. Instala Inno Setup 6 y vuelve a intentarlo.
    exit /b 1
)

"%ISCC%" /O"dist" /F"Setup" QuickMechanic.iss
if errorlevel 1 exit /b 1

echo Instalador generado: dist\Setup.exe
