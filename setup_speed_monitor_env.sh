#!/bin/bash
set -e

PROJECT_DIR="/home/sagivba-adm/src/internet-speed-monitor"
VENV_DIR="$PROJECT_DIR/speed-monitor-venv"

cd "$PROJECT_DIR"

echo "Creating required directories..."
mkdir -p "$PROJECT_DIR/src" "$PROJECT_DIR/logs" "$PROJECT_DIR/Outputs"

echo "Creating Python virtual environment: $VENV_DIR"
python3 -m venv "$VENV_DIR"

echo "Upgrading pip..."
"$VENV_DIR/bin/python" -m pip install --upgrade pip

echo "Installing requirements..."
"$VENV_DIR/bin/pip" install -r "$PROJECT_DIR/requirements.txt"

echo "Done."
echo "Virtual environment created at:"
echo "$VENV_DIR"
