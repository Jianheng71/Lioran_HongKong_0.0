#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

if ! command -v python3 >/dev/null 2>&1; then
    echo "Python 3.11 or newer is required. Install it from https://www.python.org/downloads/ and rerun setup."
    exit 1
fi

if ! python3 -c 'import sys; raise SystemExit(sys.version_info < (3, 11))'; then
    echo "Python 3.11 or newer is required."
    exit 1
fi

if ! command -v ollama >/dev/null 2>&1; then
    echo "Ollama is required. Install it from https://ollama.com/download, start Ollama, then rerun setup."
    exit 1
fi

if [ ! -x .venv/bin/python ]; then
    python3 -m venv .venv
fi

.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m playwright install chromium
.venv/bin/patchright install chromium
ollama pull hermes3:8b

if [ ! -f .env ]; then
    cp .env.example .env
fi

echo
echo "Setup complete. Run ./start.sh to launch Lioran."
