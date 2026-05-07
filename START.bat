@echo off
echo 🔥 Sistema de Detección de Incendios Forestales IoT
echo.

if not exist "backend\venv" (
    echo → Creando entorno virtual...
    python -m venv backend\venv
)

call backend\venv\Scripts\activate.bat

echo → Instalando dependencias...
pip install -r backend\requirements.txt --quiet

echo → Iniciando servidor...
echo.
python backend\main.py
pause
