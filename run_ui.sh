#!/usr/bin/env bash
# Run the VideoCreation UI from any directory.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
exec python -m streamlit run src/ui.py "$@"
