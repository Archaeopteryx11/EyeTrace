@echo off
chcp 65001 >nul
title EyeTrace - Crear ejecutable
cd /d "%~dp0"

REM --- Verificar que el zip este descomprimido ---
if not exist "%~dp0main.py" (
    echo.
    echo  ERROR: EyeTrace se esta ejecutando desde DENTRO del .zip
    echo.
    echo  1. Cierra esta ventana.
    echo  2. Clic derecho sobre EyeTrace.zip ^> "Extraer todo..." ^> Extraer.
    echo  3. Abre la carpeta EyeTrace que se creo y ejecuta este archivo desde ahi.
    echo.
    pause
    exit /b 1
)

REM Genera dist\EyeTrace\EyeTrace.exe: una carpeta que se puede
REM copiar a cualquier PC con Windows y abrir SIN instalar Python.
REM Ejecuta primero INICIAR_WINDOWS.bat una vez para crear el entorno.

if not exist ".venv\Scripts\python.exe" (
    echo Primero ejecuta INICIAR_WINDOWS.bat una vez para instalar todo
    echo y comprobar que EyeTrace funciona. Despues vuelve a ejecutar este archivo.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" -m pip install pyinstaller

".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean ^
    --name EyeTrace ^
    --add-data "face_landmarker.task;." ^
    --add-data "web;web" ^
    --collect-all mediapipe ^
    main.py

if errorlevel 1 (
    echo Hubo un error creando el ejecutable.
    pause
    exit /b 1
)

echo.
echo Listo. Copia la carpeta dist\EyeTrace completa al otro computador
echo y abre EyeTrace.exe
pause
