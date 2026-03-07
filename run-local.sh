#!/bin/bash
# Run the app locally on localhost (without Docker)
# Requires: Python 3, Node.js, and the external DB at 10.10.248.114
#
# Usage: ./run-local.sh
# Or run each service in separate terminals for better logs:
#   Terminal 1: cd engine && source .venv/bin/activate && uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
#   Terminal 2: cd api && npm run dev
#   Terminal 3: cd web && npm run dev

set -e
cd "$(dirname "$0")"

# Load .env
if [ -f .env ]; then
  set -a
  source .env
  set +a
fi

echo "Starting Spontaneous AI locally..."
echo "  Engine: http://localhost:8000"
echo "  API:    http://localhost:3000"
echo "  Web:    http://localhost:5173"
echo ""
echo "Ensure .env has POSTGRES_HOST=10.10.248.114 and ENGINE_HOST=localhost"
echo ""

# Start engine in background
(
  cd engine
  if [ -d .venv ]; then
    source .venv/bin/activate
  elif [ -d venv ]; then
    source venv/bin/activate
  fi
  export PYTHONPATH="$(pwd):$(pwd)/../shared/python"
  uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
) &
ENGINE_PID=$!

# Start API in background
(
  cd api
  npm run dev
) &
API_PID=$!

# Start web in foreground (so we can Ctrl+C to stop all)
(
  cd web
  npm run dev
) &
WEB_PID=$!

cleanup() {
  echo ""
  echo "Shutting down..."
  kill $ENGINE_PID $API_PID $WEB_PID 2>/dev/null || true
  exit 0
}
trap cleanup SIGINT SIGTERM

wait
