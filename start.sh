#!/usr/bin/env bash
# Proofread: one command to set up and run the whole project.
#
#   ./start.sh          set up anything missing and open the app on http://localhost:8501
#   ./start.sh eval     run the evaluation (writes backend/results/); add --topic <id> for a topic's test claims
#   ./start.sh setup    only install, don't start
#
# Every setup step is skipped if it has already been done, so re-running is fast.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND="$ROOT/backend"
VENV="$BACKEND/.venv"
PORT="${PROOFREAD_PORT:-8501}"
MODE="${1:-run}"

say()  { printf "\033[1;34m▸ %s\033[0m\n" "$*"; }
fail() { printf "\033[1;31m✗ %s\033[0m\n" "$*" >&2; exit 1; }

# ---------------------------------------------------------------- Python 3.11
find_python() {
  if command -v python3.11 >/dev/null 2>&1; then command -v python3.11; return; fi
  local uv="${HOME}/Library/Python/3.9/bin/uv"
  command -v uv >/dev/null 2>&1 && uv="$(command -v uv)"
  if [ -x "$uv" ] || command -v uv >/dev/null 2>&1; then
    "$uv" python find 3.11 2>/dev/null && return
  fi
  return 1
}

setup_backend() {
  if [ ! -x "$VENV/bin/python" ]; then
    local py
    if ! py="$(find_python)"; then
      say "Python 3.11 not found: installing it with uv (user folder only)"
      python3 -m pip install --user --quiet uv
      "${HOME}/Library/Python/3.9/bin/uv" python install 3.11
      py="$(find_python)" || fail "Could not install Python 3.11"
    fi
    say "Creating virtual environment with $py"
    "$py" -m venv "$VENV"
  fi
  # Reinstall packages only when requirements.txt changed since the last install.
  local stamp="$VENV/.requirements-installed"
  if [ ! -f "$stamp" ] || [ "$BACKEND/requirements.txt" -nt "$stamp" ]; then
    say "Installing Python packages (first time takes a few minutes)"
    "$VENV/bin/pip" install --quiet --upgrade pip
    "$VENV/bin/pip" install --quiet -r "$BACKEND/requirements.txt"
    touch "$stamp"
  fi
  if ! "$VENV/bin/python" -c "import en_core_web_sm" >/dev/null 2>&1; then
    say "Downloading spaCy English model"
    "$VENV/bin/python" -m spacy download en_core_web_sm >/dev/null
  fi
}

port_free() { ! lsof -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1; }

open_when_ready() {
  # Wait (in the background) until the app answers, then open the browser.
  ( for _ in $(seq 1 600); do
      if curl -s "http://localhost:$PORT/_stcore/health" >/dev/null 2>&1; then
        printf "\n\033[1;32m✓ Proofread is ready: %s\033[0m  (Ctrl+C to stop)\n\n" "$1"
        command -v open >/dev/null 2>&1 && open "$1"
        exit 0
      fi
      sleep 1
    done ) &
}

# ---------------------------------------------------------------- modes
case "$MODE" in
  setup)
    setup_backend
    say "Setup complete. Run ./start.sh to start Proofread."
    ;;

  run)
    setup_backend
    port_free "$PORT" || fail "Port $PORT is already in use. Stop the other app, or run: PROOFREAD_PORT=8502 ./start.sh"
    say "Starting Proofread on http://localhost:$PORT (the first start downloads ~640 MB of AI models)"
    open_when_ready "http://localhost:$PORT"
    cd "$ROOT"
    exec "$VENV/bin/streamlit" run streamlit_app.py --server.port "$PORT" --server.headless true --server.address localhost
    ;;

  eval)
    setup_backend
    shift || true
    cd "$BACKEND"
    exec "$VENV/bin/python" evaluate.py "$@"
    ;;

  *)
    fail "Unknown mode '$MODE'. Use: ./start.sh [run|eval|setup]"
    ;;
esac
