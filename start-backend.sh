#!/bin/bash
set -e
cd /mnt/e/Mainframe/Mainframe-Project
source ~/.venvs/mainframe-control-tower/bin/activate
export CONTROL_TOWER_DATABASE_PATH=/mnt/e/Mainframe/Mainframe-Project/backend/data/control_tower.db
export CONTROL_TOWER_CORS_ORIGINS="http://localhost:8081,http://127.0.0.1:8081,http://localhost:5173,http://127.0.0.1:5173"
exec python -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000
