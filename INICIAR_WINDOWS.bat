@echo off
chcp 65001 >nul
title EyeTrace
cd /d "%~dp0"

echo ==========================================
echo   EyeTrace - La mirada como pincel digital
echo ==========================================
echo.

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

REM --- Buscar Python (primero 3.12, luego cualquiera) ---
set "PY="
py -3.12 --version >nul 2>&1 && set "PY=py -3.12"
if not defined PY (py -3 --version >nul 2>&1 && set "PY=py -3")
if not defined PY (python --version >nul 2>&1 && set "PY=python")

if not defined PY (
    echo No se encontro Python en este computador.
    echo Instala Python 3.12 desde https://www.python.org/downloads/
    echo y marca la casilla "Add Python to PATH" durante la instalacion.
    pause
    exit /b 1
)

REM --- Crear el entorno la primera vez ---
if not exist ".venv\Scripts\python.exe" (
    echo Primera vez: preparando EyeTrace. Esto tarda unos minutos...
    %PY% -m venv .venv
    if errorlevel 1 (
        echo No se pudo crear el entorno virtual.
        pause
        exit /b 1
    )
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
)

REM --- Instalar o actualizar librerias si cambio requirements.txt ---
fc /b requirements.txt ".venv\requirements_instalados.txt" >nul 2>&1
if errorlevel 1 (
    echo Instalando librerias de EyeTrace...
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo Fallo la instalacion de dependencias. Copia el error de arriba y enviaselo a quien te paso EyeTrace.
        pause
        exit /b 1
    )
    copy /y requirements.txt ".venv\requirements_instalados.txt" >nul
)

".venv\Scripts\python.exe" main.py %*
if errorlevel 1 pause
