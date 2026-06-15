#!/usr/bin/env bash
set -e

echo "=== Fossick Intelligence — Setup ==="

# 1. .env
if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env from .env.example — add your ANTHROPIC_API_KEY before continuing."
  exit 1
fi

# 2. case_data dir
mkdir -p case_data

# 3. Build Docker forensic image
echo "[1/3] Building Docker forensic image (first run: 3-5 min)..."
docker build -t fossick-mcp -f docker/Dockerfile . --quiet

# 4. Python venv + backend deps
echo "[2/3] Installing Python dependencies..."
python3.13 -m venv venv 2>/dev/null || python3 -m venv venv
source venv/bin/activate
pip install -q -r requirements.txt

# 5. Frontend
echo "[3/3] Installing frontend dependencies..."
cd frontend && npm install --silent && cd ..

# 6. Install fossick CLI
mkdir -p ~/.local/bin
FOSSICK_ROOT="$(pwd)"
cat > ~/.local/bin/fossick << EOF
#!/bin/bash
source "${FOSSICK_ROOT}/venv/bin/activate"
exec python3 "${FOSSICK_ROOT}/fossick.py" "\$@"
EOF
chmod +x ~/.local/bin/fossick

echo ""
echo "Setup complete."
echo ""
echo "Start the backend:   source venv/bin/activate && uvicorn backend.main:app --port 8002"
echo "Start the frontend:  cd frontend && npm run dev"
echo "Run the CLI:         fossick"
echo ""
echo "Quick demo (after backend is running):"
echo "  fossick analyze case_data/nps-2008-jean.E01 --case-id demo"
