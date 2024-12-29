#!/bin/bash
# Verzeichnis des aktuellen Skripts ermitteln
SCRIPT_DIR=$(dirname "$(realpath "$0")")
echo "Wechsle in das Verzeichnis: $SCRIPT_DIR"
cd "$SCRIPT_DIR"
source venv/bin/activate
python3 UI.py