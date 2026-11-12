"""The request gate: who may call what, and who came.

Installed on the engine's FastAPI app (``engine/__init__.py``). It is its own module so
a test can put it on a small app without starting the engine.

* **Access.** With ``LESSONFORGE_ACCESS_TOKEN`` set, every request must carry it as the
  ``X-Access-Token`` header, a ``?token=`` query parameter (remembered in a cookie so the
  web client's videos and assets load) or that cookie. ``/api/compile_video`` runs Python
  posted by the client and every generation spends the metered budget, so an open public
  URL is not acceptable. Unset = localhost use.
* **Review links.** ``LESSONFORGE_REVIEW_TOKEN`` is a second, weaker secret for
  students: it can load one lesson and send one review — it cannot generate (spend),
  list, plan, read the dashboard or reach the engine. A new route is closed to it
  unless added to ``REVIEW_ALLOWED``.
* **Visitors.** Each request opens a visitor context for ``harness/analytics.py`` and
  records page loads and refusals; the routes add what was asked for.

The viewer site (``lessonforge/viewer.py``, the finished lessons on Render) installs this same gate,
so the rule cannot differ between the two: it hands in where events go (its database, not a
workspace file), its own visitor salt, and the paths open to anyone (its health check).
"""
from __future__ import annotations

import html
import hmac
import posixpath
import re

from starlette.responses import HTMLResponse, JSONResponse

from . import analytics

REVIEW_ALLOWED = (
    ("GET", re.compile(r"^/app(/.*)?$")),
    # Which kind of server this is ("studio" makes lessons, "viewer" only shows them): the app asks on start.
    ("GET", re.compile(r"^/api/harness/mode$")),
    ("GET", re.compile(r"^/lessons/.+$")),
    ("GET", re.compile(r"^/api/harness/feedback/form$")),
    ("GET", re.compile(r"^/api/harness/jobs/[A-Za-z0-9_-]+$")),
    ("POST", re.compile(r"^/api/harness/jobs/[A-Za-z0-9_-]+/feedback$")),
    # The task done by hand after the video: a student may send their answer, never read the others'.
    ("POST", re.compile(r"^/api/harness/jobs/[A-Za-z0-9_-]+/tryit$")),
    # What the player saw (a screen shown, a video started, a share watched): validated, write-only.
    ("POST", re.compile(r"^/api/harness/events$")),
    ("GET", re.compile(r"^/favicon\.ico$")),
)
TOKEN_COOKIE = "lf_token"
#: Inside a lesson folder (served whole under ``/lessons``), what no token may fetch as a file: the
#: sources' own text (``teaching_pack.json``: other people's copyright, kept for the writer only) and
#: what learners wrote (reviews, try-it answers), which a review link could otherwise read for every
#: student of that lesson. An owner reads those through the API routes.
PRIVATE_IN_LESSON = re.compile(r"^/lessons/[^/]+/(?:teaching_pack\.json|feedback|tryit)(?:/|$)", re.I)


def _same(presented: str, secret: str) -> bool:
    return bool(secret) and hmac.compare_digest(presented.encode("utf-8"), secret.encode("utf-8"))


def _wants_html(request, path: str) -> bool:
    if request.method not in ("GET", "HEAD"):
        return False
    if path.startswith(("/api/", "/static/", "/generated_videos/")):
        return False
    accept = request.headers.get("accept", "")
    if "application/json" in accept and "text/html" not in accept:
        return False
    return "text/html" in accept or path in ("/", "/app", "/app/", "/studio", "/timeline", "/bulk")


def unauthenticated_html(path: str = "", invalid: bool = False) -> str:
    esc_path = html.escape(path or "")
    action_target = esc_path if esc_path and esc_path != "/" else "/app/"
    error_banner = (
        '<div class="error-banner">The token entered was not recognized. Please check your token or request an invitation below.</div>'
        if invalid
        else ""
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <title>Adhyay Video Studio</title>
  <style>
    :root {{
      --bg: #F7F8F4;
      --card: #FFFFFF;
      --border: #D9DDD3;
      --text: #1D2320;
      --muted: #59625B;
      --primary: #2D57C8;
      --primary-hover: #1E3E96;
      --primary-light: #DCE5FB;
      --error: #DC2626;
      --error-bg: #FEF2F2;
      --error-border: #FCA5A5;
      --badge-bg: #E9ECE6;
      --shadow: 0 1px 3px rgba(29, 35, 32, 0.06), 0 8px 24px rgba(29, 35, 32, 0.08);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    }}
    @media (prefers-color-scheme: dark) {{
      :root {{
        --bg: #141816;
        --card: #222824;
        --border: #333B35;
        --text: #E6EAE4;
        --muted: #A3ACA4;
        --primary: #8EA9FF;
        --primary-hover: #ADC0FF;
        --primary-light: #26324F;
        --error: #FF7A7A;
        --error-bg: #381B1C;
        --error-border: #7F1D1D;
        --badge-bg: #2A312C;
        --shadow: 0 1px 3px rgba(0, 0, 0, 0.4), 0 8px 24px rgba(0, 0, 0, 0.3);
      }}
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: var(--bg);
      color: var(--text);
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 24px;
      line-height: 1.5;
    }}
    .card {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 16px;
      box-shadow: var(--shadow);
      max-width: 480px;
      width: 100%;
      padding: 36px 32px;
      text-align: center;
    }}
    .brand-row {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 16px;
    }}
    .brand-icon {{
      font-size: 28px;
      line-height: 1;
    }}
    .badge {{
      display: inline-block;
      font-size: 11px;
      font-weight: 600;
      letter-spacing: 0.5px;
      text-transform: uppercase;
      padding: 4px 10px;
      border-radius: 999px;
      background: var(--badge-bg);
      color: var(--muted);
      margin-bottom: 16px;
    }}
    h1 {{
      font-size: 24px;
      font-weight: 700;
      letter-spacing: -0.3px;
      margin-bottom: 8px;
    }}
    .tagline {{
      font-size: 14px;
      color: var(--muted);
      margin-bottom: 24px;
    }}
    .desc {{
      font-size: 13.5px;
      color: var(--muted);
      background: var(--bg);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 12px 14px;
      margin-bottom: 24px;
      text-align: left;
    }}
    .error-banner {{
      background: var(--error-bg);
      border: 1px solid var(--error-border);
      color: var(--error);
      border-radius: 10px;
      padding: 10px 14px;
      font-size: 13px;
      margin-bottom: 20px;
      text-align: left;
    }}
    .form-group {{
      text-align: left;
      margin-bottom: 20px;
    }}
    label {{
      display: block;
      font-size: 12.5px;
      font-weight: 600;
      margin-bottom: 6px;
      color: var(--text);
    }}
    .input-row {{
      display: flex;
      gap: 8px;
    }}
    input[type="password"] {{
      flex: 1;
      padding: 10px 14px;
      border: 1px solid var(--border);
      border-radius: 8px;
      font-size: 14px;
      background: var(--card);
      color: var(--text);
      outline: none;
      transition: border-color 0.15s;
    }}
    input[type="password"]:focus {{
      border-color: var(--primary);
      box-shadow: 0 0 0 3px var(--primary-light);
    }}
    button[type="submit"] {{
      padding: 10px 18px;
      background: var(--primary);
      color: #FFFFFF;
      border: 0;
      border-radius: 8px;
      font-size: 14px;
      font-weight: 600;
      cursor: pointer;
      white-space: nowrap;
      transition: background 0.15s;
    }}
    @media (prefers-color-scheme: dark) {{
      button[type="submit"] {{ color: #141816; }}
    }}
    button[type="submit"]:hover {{
      background: var(--primary-hover);
    }}
    .divider {{
      display: flex;
      align-items: center;
      margin: 24px 0 20px;
      color: var(--muted);
      font-size: 12px;
    }}
    .divider::before, .divider::after {{
      content: "";
      flex: 1;
      border-bottom: 1px solid var(--border);
    }}
    .divider span {{
      padding: 0 10px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }}
    .actions {{
      display: flex;
      flex-direction: column;
      gap: 10px;
    }}
    .btn-secondary {{
      display: inline-block;
      padding: 10px 16px;
      background: transparent;
      border: 1px solid var(--border);
      border-radius: 8px;
      color: var(--text);
      font-size: 13.5px;
      font-weight: 600;
      text-decoration: none;
      transition: background 0.15s, border-color 0.15s;
    }}
    .btn-secondary:hover {{
      background: var(--badge-bg);
      border-color: var(--muted);
    }}
    .muted-link {{
      font-size: 12.5px;
      color: var(--muted);
      text-decoration: none;
      margin-top: 4px;
    }}
    .muted-link:hover {{
      text-decoration: underline;
    }}
  </style>
</head>
<body>
  <div class="card">
    <div class="brand-row">
      <span class="brand-icon">🎬</span>
    </div>
    <div>
      <span class="badge">Early Stage · By Invitation</span>
    </div>
    <h1>Adhyay Video Studio</h1>
    <p class="tagline">Narrated mathematical animations and STEM lesson generator</p>

    <div class="desc">
      The video studio is currently in early stage and by invitation only. If you have an access token or review link, enter it below to proceed.
    </div>

    {error_banner}

    <form method="GET" action="{action_target}" id="tokenForm">
      <div class="form-group">
        <label for="tokenInput">Access token or review link</label>
        <div class="input-row">
          <input type="password" id="tokenInput" name="token" placeholder="Paste access token or ?token= link..." autocomplete="current-password" autofocus required>
          <button type="submit" id="submitBtn">Enter →</button>
        </div>
      </div>
    </form>

    <div class="divider"><span>or</span></div>

    <div class="actions">
      <a href="https://adhyay.app/#contact" class="btn-secondary" target="_blank" rel="noopener">Request Access on Adhyay ↗</a>
      <a href="https://dev.adhyay.app" class="muted-link">← Return to Lesson Board</a>
    </div>
  </div>

  <script>
    document.getElementById('tokenForm').addEventListener('submit', function(e) {{
      var input = document.getElementById('tokenInput');
      var val = (input.value || '').trim();
      if (!val) return;
      var m = val.match(/[?&]token=([^&#]+)/);
      if (m) val = decodeURIComponent(m[1]);
      input.value = val;
    }});
  </script>
</body>
</html>"""


def install(app, access_token: str = "", review_token: str = "", *, begin=None, note=None, open_paths=()) -> None:
    """``begin``/``note``: how a visitor is recognised and an event kept (``analytics.begin``/``note`` unless
    given). ``open_paths``: path prefixes answered without a token and not counted (the viewer's health check)."""
    access_token, review_token = (access_token or "").strip(), (review_token or "").strip()
    begin, note = begin or analytics.begin, note or analytics.note
    open_paths = tuple(open_paths)

    def role_of(presented: str) -> str:
        """The caller: ``owner``, ``review``, ``local`` (no token configured) or an empty string (refused)."""
        if not access_token:
            return "local"
        return "owner" if _same(presented, access_token) else "review" if _same(presented, review_token) else ""

    @app.middleware("http")
    async def _gate(request, call_next):
        path = request.url.path
        if open_paths and path.startswith(open_paths):
            return await call_next(request)
        query_token = request.query_params.get("token")
        presented = request.headers.get("x-access-token") or query_token or request.cookies.get(TOKEN_COOKIE) or ""
        role = role_of(presented)
        method = "GET" if request.method == "HEAD" else request.method
        try:
            ctx, fresh = begin(request.headers, request.cookies, path, role or "none",
                               request.client.host if request.client else "")
        except Exception:  # counting visitors must never refuse one
            ctx, fresh = None, None
        if not role:
            if _wants_html(request, path):
                response = HTMLResponse(
                    unauthenticated_html(path=path, invalid=bool(query_token)),
                    status_code=401,
                    headers={"WWW-Authenticate": 'Bearer realm="Adhyay Videos"'},
                )
            else:
                response = JSONResponse(
                    {"detail": "access token required (X-Access-Token header or ?token=)"},
                    status_code=401,
                )
        elif PRIVATE_IN_LESSON.match(posixpath.normpath(path)):
            response = JSONResponse({"detail": "not found"}, status_code=404)
        elif role == "review" and not any(method == m and pattern.match(path) for m, pattern in REVIEW_ALLOWED):
            response = JSONResponse({"detail": "a review link can only open its lesson and send a review"},
                                    status_code=403)
        else:
            response = await call_next(request)
        if ctx and request.method != "OPTIONS":
            event = analytics.page_event(method, path, response.status_code)
            if event:
                note(event, ctx, path=path[:80] if event == "blocked" else None)
        https = request.headers.get("x-forwarded-proto", request.url.scheme) == "https"
        if role in ("owner", "review") and query_token and request.cookies.get(TOKEN_COOKIE) != presented:
            response.set_cookie(TOKEN_COOKIE, presented, httponly=True, samesite="lax", secure=https,
                                max_age=7 * 24 * 3600)
        if role and ctx and fresh:
            response.set_cookie(analytics.COOKIE, ctx["visitor"], httponly=True, samesite="lax", secure=https,
                                max_age=analytics.COOKIE_MAX_AGE)
        return response
