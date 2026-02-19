#!/usr/bin/env bash
set -euo pipefail

CMD=${1:-serve}

kill_all() {
    kill `ps -a | grep python | awk '{print $1}'`
}

serve() {
  (cd frontend; python3 -m http.server 8000) &
  FRONT_PID=$!
  (cd backend; ../.venv/bin/uvicorn main:app --host 0.0.0.0 --port 9000) &
  BACK_PID=$!
  trap "kill $FRONT_PID $BACK_PID 2>/dev/null" EXIT
  wait
}

run_tests() {
  if [ ! -x ".venv/bin/python" ]; then
    echo "Python venv not found. Please create it before running tests." >&2
    exit 1
  fi
  ./.venv/bin/python tests/run_tests.py
}

case "$CMD" in
  serve)
    serve
    ;;
  test)
    run_tests
    ;;
  kill)
    kill_all
    ;;
  *)
    echo "Usage: ./run.sh [serve|test]" >&2
    exit 1
    ;;
esac
