#!/bin/sh
set -eu
cd /app/code
python -m backend.db.init
cd frontend
# Serve Reflex's prebuilt frontend and Python API from the same ASGI app.
export PYTHONPATH="/app/code${PYTHONPATH:+:$PYTHONPATH}"
export REFLEX_ENV_MODE=prod
export __REFLEX_SKIP_COMPILE=true
export __REFLEX_MOUNT_FRONTEND_COMPILED_APP=true
exec granian --interface asgi --factory --host 0.0.0.0 --port "${PORT:-10000}" healthify.healthify:app
