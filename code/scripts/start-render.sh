#!/bin/sh
set -eu
cd /app/code
python -m backend.db.init
cd frontend
exec reflex run --env prod --backend-host 0.0.0.0 --backend-port "${PORT:-10000}"
