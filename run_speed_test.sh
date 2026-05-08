#!/bin/bash
set -e

PROJECT_DIR="/home/sagivba-adm/src/internet-speed-monitor"
PYTHON_BIN="$PROJECT_DIR/speed-monitor-venv/bin/python"
SCRIPT_FILE="$PROJECT_DIR/src/internet_speed_monitor.py"
OUTPUT_DIR="$PROJECT_DIR/Outputs"
LOG_DIR="$PROJECT_DIR/logs"

mkdir -p "$OUTPUT_DIR" "$LOG_DIR"

cd "$PROJECT_DIR"

"$PYTHON_BIN" "$SCRIPT_FILE" \
  --once \
  --csv "$OUTPUT_DIR/internet_speed_results.csv" \
  --html "$OUTPUT_DIR/internet_speed_report.html"
