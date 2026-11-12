# The viewer site for Render (lessonforge/viewer.py): the built web app and the finished lessons, and nothing
# that makes them: no Manim, no LaTeX, no browser, no models. Lessons are made on the GPU machine and published
# to Cloudflare R2 (`lessonforge publish`); what viewers write goes to Cloudflare D1.
#
# Built from the REPOSITORY ROOT (deploy/render.yaml: dockerContext ".", dockerfilePath ./lessonforge/deploy/Dockerfile):
#   docker build -f lessonforge/deploy/Dockerfile -t lessonforge-viewer .
# Run it on this machine without Cloudflare (a folder stands in for R2 and D1):
#   docker run -p 10000:10000 -e LESSONFORGE_CLOUD_DIR=/cloud -v /some/folder:/cloud lessonforge-viewer
# Guide: lessonforge/docs/DEPLOY_RENDER_VIEWER.md

# ── 1. the web app (clients/lessonforge-app → dist/, served at /app) ──
FROM node:20-bookworm-slim AS web
ENV EXPO_NO_TELEMETRY=1 CI=1
WORKDIR /build
COPY lessonforge/clients/lessonforge-app/package.json lessonforge/clients/lessonforge-app/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY lessonforge/clients/lessonforge-app/ ./
RUN npx expo export --platform web --output-dir dist

# ── 2. the viewer: Python with only what it needs ──
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /srv
# The versions the viewer was tested with (lessonforge/tests/unit/test_viewer.py, 2026-10-15).
RUN pip install "fastapi==0.142.2" "starlette==1.7.0" "uvicorn==0.54.0" "boto3==1.43.114" "httpx==0.28.1" \
        "pydantic==2.13.5"
# The package alone, without its dependencies (those are the studio's: Manim, the voices, the models).
COPY lessonforge/pyproject.toml lessonforge/README.md ./lessonforge/
COPY lessonforge/src ./lessonforge/src
RUN pip install --no-deps ./lessonforge && rm -rf ./lessonforge \
    && python -c "import lessonforge.viewer, sys; assert 'manim' not in sys.modules"
COPY --from=web /build/dist /srv/web
RUN useradd --create-home --uid 10001 viewer
USER viewer
# Nothing on this disk outlives a deploy: lessons are in R2, what viewers write in D1.
ENV LESSONFORGE_WEB_APP=/srv/web LESSONFORGE_HOME=/tmp/lessonforge PORT=10000
EXPOSE 10000
# Render sets PORT; --proxy-headers so https is recognised behind its proxy (the token cookie is then Secure).
CMD ["sh", "-c", "exec uvicorn lessonforge.viewer:app --host 0.0.0.0 --port ${PORT:-10000} --proxy-headers --forwarded-allow-ips '*'"]
