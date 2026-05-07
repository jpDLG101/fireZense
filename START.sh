#!/bin/bash

echo "🔥 Sistema de Detección de Incendios Forestales IoT"
echo ""

# Recrear venv si no existe o si el Python interno está roto
if [ ! -d "backend/venv" ] || ! backend/venv/bin/pip --version &>/dev/null; then
    echo "→ Creando entorno virtual..."
    rm -rf backend/venv
    python3 -m venv backend/venv
fi

# Activar venv
source backend/venv/bin/activate

echo "→ Verificando dependencias..."
pip install -r backend/requirements.txt --quiet

echo "→ Iniciando servidor..."
echo ""
python3 backend/main.py
