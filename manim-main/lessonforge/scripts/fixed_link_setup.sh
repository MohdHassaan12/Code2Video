#!/bin/bash
# One-time setup of a link that keeps its address: a named Cloudflare tunnel to this server.
#
#   bash scripts/fixed_link_setup.sh lessons.example.com
#
# Needs a domain on your Cloudflare account (the free plan is enough). It asks you to sign in to
# Cloudflare once in a browser, creates the tunnel "lessonforge", points the name at it, and writes
# LESSONFORGE_TUNNEL_CONFIG and LESSONFORGE_PUBLIC_URL into .env. From then on
# scripts/public_link.sh uses this tunnel, and the link is the same after every restart and reboot.
#
# Everything lives in <workspace>/tunnel/ and ~/.cloudflared/. The machine's own cloudflared
# service (/etc/cloudflared) is a different tunnel and is never touched.
set -eu
HOST="${1:-}"
if [ -z "$HOST" ] || [[ "$HOST" == http* ]] || [[ "$HOST" != *.* ]]; then
  echo "usage: bash scripts/fixed_link_setup.sh <name.yourdomain.com>  (no https://)"; exit 2
fi
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
set -a; . ./.env; set +a
export LESSONFORGE_HOME="${LESSONFORGE_HOME:-$ROOT/lessonforge_workspace}"
PORT="${LESSONFORGE_PORT:-5000}"
NAME="${LESSONFORGE_TUNNEL_NAME:-lessonforge}"
DIR="$LESSONFORGE_HOME/tunnel"; mkdir -p "$DIR"

command -v cloudflared >/dev/null || { echo "cloudflared is not installed"; exit 1; }

# 1. Sign in once (opens a browser page; on a server without one, open the printed link elsewhere).
[ -f "$HOME/.cloudflared/cert.pem" ] || cloudflared tunnel login

# 2. The tunnel (kept if it already exists).
if ! cloudflared tunnel info "$NAME" >/dev/null 2>&1; then
  cloudflared tunnel create "$NAME"
fi
ID="$(cloudflared tunnel list -o json | python3 -c "import sys,json; print(next(t['id'] for t in json.load(sys.stdin) if t['name']=='$NAME'))")"
CREDS="$HOME/.cloudflared/$ID.json"
[ -f "$CREDS" ] || { echo "no credentials file at $CREDS"; exit 1; }

# 3. The name points at the tunnel (a CNAME on your domain; kept if it is already there).
cloudflared tunnel route dns "$NAME" "$HOST" || true

# 4. Its own config file, so cloudflared never reads /etc/cloudflared.
cat > "$DIR/config.yml" <<CFG
tunnel: $ID
credentials-file: $CREDS
protocol: http2
ingress:
  - hostname: $HOST
    service: http://127.0.0.1:$PORT
  - service: http_status:404
CFG

# 5. Remember it in .env (replacing earlier lines).
sed -i '/^LESSONFORGE_TUNNEL_CONFIG=/d; /^LESSONFORGE_PUBLIC_URL=/d' .env
printf 'LESSONFORGE_TUNNEL_CONFIG=%s\nLESSONFORGE_PUBLIC_URL=https://%s\n' "$DIR/config.yml" "$HOST" >> .env
tail -2 .env

echo
echo "Done. Now run:  bash scripts/public_link.sh --new"
echo "Your link from now on:  https://$HOST/app/?token=<your access token>"
