@echo off
title PeliBot
echo Iniciando PeliBot...

:: Verificar que Python esta instalado
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python no esta instalado o no esta en el PATH.
    echo Descargalo desde https://python.org/downloads
    pause
    exit /b 1
)

:: Ir a la carpeta del script
cd /d "%~dp0"

:: Instalar dependencias si faltan
echo Verificando dependencias...
pip install -r requirements.txt --quiet

:: Iniciar el bot
echo Bot iniciado. No cierres esta ventana.
echo Para detenerlo presiona Ctrl+C
echo.
python main.py

pause
