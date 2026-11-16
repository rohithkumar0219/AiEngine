# ── Stage 1: Build Frontend ──────────────────────────────────────────────────
FROM node:22-alpine AS frontend-builder
WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# ── Stage 2: Production Python Runtime ───────────────────────────────────────
FROM python:3.12-slim AS runner

WORKDIR /app

# Install security updates and curl for container health probes
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Install Python production dependencies
COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r backend/requirements.txt

# Copy backend application source code
COPY backend/ ./backend/

# Copy built frontend production bundle into place
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Set Python search paths
ENV PYTHONPATH="backend:backend/subagents/src"
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

# Expose production port
EXPOSE 8000

# Container healthcheck probe
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://127.0.0.1:8000/health || exit 1

# Run with Uvicorn ASGI server
CMD ["python", "-m", "uvicorn", "backend.api:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]

