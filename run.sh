#!/usr/bin/env bash
# BankSym run script (macOS / Linux).
# Usage: ./run.sh [start|stop|restart|status]
#   start   - create venv (if needed), install deps, start the server if not already running
#   stop    - stop the running server
#   restart - stop then start
#   status  - report whether the server is running
set -euo pipefail

# --- Configuration -----------------------------------------------------------
HOST="${BANKSYM_HOST:-127.0.0.1}"
PORT="${BANKSYM_PORT:-8000}"
APP="banksym.api.app:app"

# Resolve the directory this script lives in, so it works from anywhere.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV_DIR=".venv"
PY="$VENV_DIR/bin/python"
PID_FILE=".banksym.pid"
LOG_FILE="banksym.log"
DEPS_STAMP="$VENV_DIR/.deps-installed"

# --- Helpers -----------------------------------------------------------------
is_running() {
  [ -f "$PID_FILE" ] || return 1
  local pid
  pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null
}

ensure_venv() {
  if [ ! -x "$PY" ]; then
    echo "Creating virtual environment in $VENV_DIR ..."
    if command -v python3 >/dev/null 2>&1; then
      python3 -m venv "$VENV_DIR"
    else
      python -m venv "$VENV_DIR"
    fi
  fi
}

ensure_deps() {
  # Reinstall when pyproject.toml is newer than the stamp (or stamp is missing).
  if [ ! -f "$DEPS_STAMP" ] || [ pyproject.toml -nt "$DEPS_STAMP" ]; then
    echo "Installing dependencies ..."
    "$PY" -m pip install --quiet --upgrade pip
    "$PY" -m pip install --quiet -e ".[dev]"
    touch "$DEPS_STAMP"
  fi
}

# --- Commands ----------------------------------------------------------------
start() {
  if is_running; then
    echo "BankSym is already running (PID $(cat "$PID_FILE")) at http://$HOST:$PORT"
    return 0
  fi
  ensure_venv
  ensure_deps
  echo "Starting BankSym at http://$HOST:$PORT ..."
  # Start uvicorn detached; record its PID.
  nohup "$PY" -m uvicorn "$APP" --host "$HOST" --port "$PORT" \
    >"$LOG_FILE" 2>&1 &
  echo $! >"$PID_FILE"
  sleep 1
  if is_running; then
    echo "Started (PID $(cat "$PID_FILE")). Logs: $LOG_FILE  |  Docs: http://$HOST:$PORT/docs"
  else
    echo "Failed to start. Check $LOG_FILE:" >&2
    tail -n 20 "$LOG_FILE" >&2 || true
    rm -f "$PID_FILE"
    exit 1
  fi
}

stop() {
  if ! is_running; then
    echo "BankSym is not running."
    rm -f "$PID_FILE"
    return 0
  fi
  local pid
  pid="$(cat "$PID_FILE")"
  echo "Stopping BankSym (PID $pid) ..."
  kill "$pid" 2>/dev/null || true
  for _ in $(seq 1 10); do
    is_running || break
    sleep 0.5
  done
  if is_running; then
    echo "Process did not exit; sending SIGKILL ..."
    kill -9 "$pid" 2>/dev/null || true
  fi
  rm -f "$PID_FILE"
  echo "Stopped."
}

status() {
  if is_running; then
    echo "BankSym is running (PID $(cat "$PID_FILE")) at http://$HOST:$PORT"
  else
    echo "BankSym is not running."
  fi
}

case "${1:-start}" in
  start)   start ;;
  stop)    stop ;;
  restart) stop; start ;;
  status)  status ;;
  *)
    echo "Usage: $0 [start|stop|restart|status]" >&2
    exit 2
    ;;
esac
