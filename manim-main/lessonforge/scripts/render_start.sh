#!/usr/bin/env bash
# Start the server in a container (Render, or plain `docker run`). It listens on every address, so it
# refuses to start without LESSONFORGE_ACCESS_TOKEN: /api/compile_video runs posted Python and every
# lesson spends the OpenRouter budget (harness/gate.py).
set -euo pipefail
if [ -z "${LESSONFORGE_ACCESS_TOKEN:-}" ]; then
    echo "LESSONFORGE_ACCESS_TOKEN is not set; refusing to serve on a public address." >&2
    exit 1
fi
mkdir -p "${LESSONFORGE_HOME:-/data/workspace}"
exec lessonforge serve --host 0.0.0.0 --port "${PORT:-5000}"
