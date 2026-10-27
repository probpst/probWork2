#!/bin/sh
# Parametric Hull Form Designer (Linux / macOS): creates a virtual environment on first start.
cd "$(dirname "$0")"
[ -d .venv ] || { python3 -m venv .venv && .venv/bin/pip install -r requirements.txt; }
exec .venv/bin/python main.py "$@"
