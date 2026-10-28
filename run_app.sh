#!/usr/bin/env bash
# Startup script for Bank Statement Fraud Detection Dashboard

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ -d ".venv" ]; then
    echo "Activating virtual environment..."
    source .venv/bin/activate
fi

echo "Starting Forensic Bank Statement Fraud Detection Dashboard on http://localhost:8501 ..."
streamlit run app.py
