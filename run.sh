#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -d ".venv" ]; then
    echo "[ERROR] Virtual environment not found. Please run install.sh first."
    exit 1
fi

source .venv/bin/activate
python main.py
EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    echo "[ERROR] Application exited with error code $EXIT_CODE."
fi

exit $EXIT_CODE
