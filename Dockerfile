# Dev image for Healthify: same steps as run_healthify.bat, but identical on
# every laptop. Python is pinned to 3.12 to match code/specs/tech-stack.md.
FROM python:3.12-slim

# Reflex downloads its own JS runtime (bun) on first run and needs curl + unzip for that.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl unzip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy only requirements first so Docker caches the pip layer: editing app code
# doesn't trigger a reinstall, only changing requirements.txt does.
COPY code/requirements.txt code/requirements.txt
RUN pip install --no-cache-dir -r code/requirements.txt

# The real code. In development compose.yaml mounts the repo over /app anyway,
# so this copy only matters if someone runs the image without compose.
COPY . .

# 3000 = frontend, 8000 = backend (Reflex defaults)
EXPOSE 3000 8000

# Same as the .bat: make sure DB tables exist (safe to re-run), then start Reflex.
CMD ["sh", "-c", "cd /app/code && python -m backend.db.init; cd /app/code/frontend && reflex run"]
