#!/bin/bash
# Pokemon Tracker for Mac. Double-click to start (the first time: right-click > Open).
cd "$(dirname "$0")"
if ! command -v python3 >/dev/null 2>&1 || ! python3 -c "import venv" >/dev/null 2>&1; then
  echo "Python 3 isn't installed yet."
  echo "Install it from https://www.python.org/downloads/ and double-click this file again."
  read -r -p "Press Enter to close..."
  exit 1
fi
if [ ! -d .venv ]; then
  echo "First run: setting things up, this takes a minute..."
  python3 -m venv .venv || exit 1
  .venv/bin/python -m pip install --upgrade pip
  .venv/bin/python -m pip install -r requirements.txt || { read -r -p "Press Enter to close..."; exit 1; }
fi
.venv/bin/python main.py "$@"
