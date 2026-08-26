#!/usr/bin/env bash
# ==============================================================================
# WildEye Startup Script for Unix / Linux / macOS
# ==============================================================================

# Ensure script runs from the repository root directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR" || exit 1

echo "=================================================="
echo "🐾 Starting WildEye Platform (Linux / macOS)"
echo "=================================================="

# 1. Environment Configuration Check
if [ ! -f ".env" ] && [ -f ".env.example" ]; then
    echo "[!] .env file not found. Creating from .env.example..."
    cp .env.example .env
fi

# 2. Activate Python Virtual Environment
VENV_DIR="$SCRIPT_DIR/venv"

if [ -d "$VENV_DIR" ]; then
    echo "[1/4] Activating virtual environment..."
    # shellcheck disable=SC1091
    source "$VENV_DIR/bin/activate"
else
    echo "[1/4] Virtual environment not found at $VENV_DIR"
    echo "[!] Creating virtual environment..."
    python3 -m venv "$VENV_DIR" || { echo "[ERROR] Failed to create virtual environment."; exit 1; }
    # shellcheck disable=SC1091
    source "$VENV_DIR/bin/activate"
fi

# 3. Check & Install Dependencies
echo "[2/4] Checking Python dependencies..."
MISSING_DEPS=0
python -c "import django, rest_framework, pymysql, paho.mqtt, dotenv" 2>/dev/null || MISSING_DEPS=1

if [ $MISSING_DEPS -ne 0 ]; then
    echo "[!] Missing dependencies detected. Installing from requirements.txt..."
    pip install -r requirements.txt || { echo "[ERROR] Dependency installation failed."; exit 1; }
else
    echo "[✓] Dependencies verified."
fi

# 4. Apply Database Migrations
echo "[3/4] Applying Django database migrations..."
python backend/manage.py migrate || echo "[WARNING] Database migration failed. Please check MySQL server and .env settings."

# 5. Start Background MQTT Subscriber and Django Dev Server
echo "[4/4] Starting Background MQTT Subscriber & Django Web Portal..."
echo "--------------------------------------------------"

# Cleanup handler for background MQTT process on exit
cleanup() {
    echo ""
    echo "[!] Shutting down WildEye background services..."
    if [ -n "$MQTT_PID" ] && kill -0 "$MQTT_PID" 2>/dev/null; then
        echo "[!] Stopping background MQTT subscriber (PID: $MQTT_PID)..."
        kill "$MQTT_PID" 2>/dev/null || true
    fi
    echo "[✓] WildEye shutdown complete."
}
trap cleanup EXIT INT TERM

# Start MQTT subscriber daemon in background
python backend/manage.py run_mqtt_subscriber &
MQTT_PID=$!
echo "[✓] MQTT Subscriber Daemon started in background (PID: $MQTT_PID)."

# Attempt to open browser automatically in background
(
    sleep 3
    if command -v xdg-open >/dev/null 2>&1; then
        xdg-open "http://127.0.0.1:8000" >/dev/null 2>&1
    elif command -v open >/dev/null 2>&1; then
        open "http://127.0.0.1:8000" >/dev/null 2>&1
    fi
) &

# Start Django development server
echo "[✓] Launching Django Web Portal on http://127.0.0.1:8000"
echo "Press Ctrl+C to stop all services."
echo "--------------------------------------------------"
python backend/manage.py runserver 0.0.0.0:8000
