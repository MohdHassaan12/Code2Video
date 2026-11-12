# lessonforge server in one image: the lesson API, the renderer (Manim, LaTeX, ffmpeg, Chromium) and the web app.
# Built by Render from ../render.yaml; also runs anywhere Docker does:
#   docker build -t lessonforge lessonforge && docker run -p 5000:5000 -e LESSONFORGE_ACCESS_TOKEN=... lessonforge

# ── 1. The web app (clients/lessonforge-app) → static files served at /app ──────────────────────
FROM node:20-slim AS app
WORKDIR /src
COPY clients/lessonforge-app/package.json clients/lessonforge-app/package-lock.json ./
# npm can exit 0 after a failed install ("Exit handler never called"), so check that expo arrived.
RUN npm ci --no-audit --no-fund && test -x node_modules/.bin/expo
COPY clients/lessonforge-app/ ./
RUN npx --no-install expo export --platform web --output-dir dist

# ── 2. The server ──────────────────────────────────────────────────────────────────────────────
FROM python:3.12-slim-bookworm

# System packages from docs/DEV_SETUP.md section 1. texlive-fonts-extra is left out: it adds about
# 1.5 GB and Manim's default LaTeX template needs only the recommended fonts and cm-super.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential pkg-config libcairo2-dev libpango1.0-dev ffmpeg \
        texlive texlive-latex-extra texlive-fonts-recommended cm-super dvisvgm \
        wamerican fonts-lato chromium sox git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    LESSONFORGE_CHROME=/usr/bin/chromium \
    LESSONFORGE_HOME=/data/workspace \
    LESSONFORGE_WEB_APP=/opt/lessonforge-app \
    HARNESS_WORKERS=1 \
    PORT=5000

WORKDIR /srv/lessonforge
COPY requirements.lock.txt ./
RUN pip install -r requirements.lock.txt
COPY . .
RUN pip install --no-deps -e .
COPY --from=app /src/dist /opt/lessonforge-app

EXPOSE 5000
CMD ["bash", "scripts/render_start.sh"]
