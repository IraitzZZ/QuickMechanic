@echo off
REM ---------------------------------------------------------------------------
REM  Compila Quick Mechanic a un unico QuickMechanic.exe (codigo empaquetado)
REM ---------------------------------------------------------------------------
setlocal
cd /d "%~dp0"

echo === Instalando dependencias ===
python -m pip install --upgrade -r requirements.txt || goto :error

echo.
echo === Compilando QuickMechanic.exe (tarda entre 30 y 60 segundos) ===
set "ICON_ARGS="
if exist "icono.ico" set "ICON_ARGS=--icon=icono.ico --add-data=icono.ico;."
python -m PyInstaller --noconfirm --clean --onefile --windowed ^
    --name QuickMechanic --paths . ^
    %ICON_ARGS% --exclude-module PyQt6.QtWebEngineCore launcher.py || goto :error

echo.
echo Listo. El ejecutable portable esta en: dist\QuickMechanic.exe
echo.
echo Para crear Setup.exe instala Inno Setup 6 y ejecuta build_installer.bat.
echo El instalador actualiza los archivos de la app y conserva perfiles/configuracion en %%APPDATA%%.
echo.
echo Para comprobar que funciona sin abrir la ventana:
echo     dist\QuickMechanic.exe --selftest --report informe.txt
echo.
pause
exit /b 0

:error
echo.
echo *** Ha fallado la compilacion. Revisa los mensajes de arriba. ***
pause
exit /b 1
