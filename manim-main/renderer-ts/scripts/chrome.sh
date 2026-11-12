#!/bin/sh
# Revideo always adds --single-process, which crashes this Chromium build; drop it.
for a; do shift; [ "$a" = "--single-process" ] || set -- "$@" "$a"; done
CHROME_BIN="${CHROME:-$(command -v google-chrome || command -v chromium || command -v chromium-browser || echo /opt/pw-browsers/chromium)}"
exec "$CHROME_BIN" "$@"
