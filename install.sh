#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "[INFO] Checking for Python..."
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python is not installed or not in your PATH."
    echo "Please install Python 3.11+ and try again."
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "[INFO] Found Python $PYTHON_VERSION"

if [ ! -d ".venv" ]; then
    echo "[INFO] Creating virtual environment..."
    python3 -m venv .venv
    if [ $? -ne 0 ]; then
        echo "[ERROR] Failed to create virtual environment."
        exit 1
    fi
fi

echo "[INFO] Activating virtual environment..."
source .venv/bin/activate
if [ $? -ne 0 ]; then
    echo "[ERROR] Failed to activate virtual environment."
    exit 1
fi

echo "[INFO] Installing dependencies..."
pip install .
if [ $? -ne 0 ]; then
    echo "[ERROR] Failed to install dependencies."
    exit 1
fi

echo "[SUCCESS] Installation complete! You can now use ./run.sh to start the application."
