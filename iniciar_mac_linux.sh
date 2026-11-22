#!/usr/bin/env bash
# EyeTrace - lanzador para macOS y Linux
cd "$(dirname "$0")" || exit 1

PY=""
for candidato in python3.12 python3 python; do
    if command -v "$candidato" >/dev/null 2>&1; then
        PY="$candidato"
        break
    fi
done

if [ -z "$PY" ]; then
    echo "No se encontro Python. Instala Python 3.12 desde https://www.python.org/downloads/"
    exit 1
fi

if [ ! -x ".venv/bin/python" ]; then
    echo "Primera vez: preparando EyeTrace. Esto tarda unos minutos..."
    "$PY" -m venv .venv || exit 1
    .venv/bin/python -m pip install --upgrade pip
fi

# Instalar o actualizar librerias si cambio requirements.txt
if ! cmp -s requirements.txt .venv/requirements_instalados.txt; then
    echo "Instalando librerias de EyeTrace..."
    if ! .venv/bin/python -m pip install -r requirements.txt; then
        echo "Fallo la instalacion de dependencias."
        exit 1
    fi
    cp requirements.txt .venv/requirements_instalados.txt
fi

exec .venv/bin/python main.py "$@"
