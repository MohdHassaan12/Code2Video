# Running lessonforge on Render

## Two ways to be on Render: choose one

| | **The viewer** (`lessonforge/deploy/render.yaml`, guide: [DEPLOY_RENDER_VIEWER.md](DEPLOY_RENDER_VIEWER.md)) | **The whole studio** (`render.yaml` at the root, this page) |
|---|---|---|
| What runs on Render | the app and the finished lessons; nothing is made there | the server, the renderer and the app: lessons are made there |
| Where lessons are made | on the GPU machine, which publishes each finished one | on Render's one CPU, one lesson at a time |
| Storage | Cloudflare R2 (lesson files) and D1 (reviews, plays) | a 10 GB Render disk |
| The lessons already made | all of them, after one `lessonforge publish --all` | none: Render's disk starts empty |
| Render plan | free (sleeps when idle) or starter | standard (2 GB) plus the disk |
| Blueprint Path when creating it | `lessonforge/deploy/render.yaml` | leave empty |

The two do not share anything and can both exist; most likely only one is wanted. The rest of this page is the
whole studio.

**If you use this one:** Render's generated `LESSONFORGE_ACCESS_TOKEN` is base64 and may contain `+`, which turns
into a space in a link's `?token=`. If the link answers 401, replace the token in the Environment tab with one made
of letters, digits, `-` and `_` (`python3 -c "import secrets; print(secrets.token_urlsafe(24))"`).

## The whole studio

The server, the renderer and the app run as one Docker web service on [Render](https://render.com), described by
[`../../render.yaml`](../../render.yaml). Lessons and the spend ledger live on a Render disk, so a restart keeps them.

## Set it up (once)

1. On Render: **New → Blueprint**, pick this repository. Render reads `render.yaml`.
2. Fill in the keys it asks for. `OPENROUTER_API_KEY` is the one that matters; the diagram and speech service
   addresses can stay empty (lessons then use the built-in voice and no diagram service).
3. **Apply**. The first build takes about 15 to 20 minutes (LaTeX and Chromium are large).
4. Open the service's **Environment** tab, copy `LESSONFORGE_ACCESS_TOKEN`, and open
   `https://<your-service>.onrender.com/app/?token=<that token>` once. The browser remembers it.

Deploys are manual (`autoDeploy: false`): press **Manual Deploy** after merging. Check `GET /api/harness/jobs`
first, because a deploy restarts the server and a lesson being made is lost (it shows as "start it again").

## What it costs and where it falls short

| | |
|---|---|
| Plan | `standard` (2 GB memory, 1 CPU), about 25 USD a month, plus about 2.50 USD a month for the 10 GB disk. The free and 512 MB plans are not enough: Manim, LaTeX and Chromium run out of memory, and the free plan has no disk and sleeps when idle, which stops lessons mid-way. |
| Speed | One CPU renders one lesson at a time (`HARNESS_WORKERS=1`), slower than a desktop. Raise the plan for more. |
| One copy | A service with a disk runs as a single instance and has a few seconds of downtime on each deploy. |
| Changing addresses | `DIAGRAM_API_URL` and `INDIC_TTS_URL` point at services on the owner's own machine whose tunnel addresses change; update them in the Environment tab when they do. |
| The improver | `scripts/agent/improve.sh` uses Claude Code signed in to a Pro subscription. It stays on the owner's own machine; it does not run on Render. |
| Fonts | The image leaves out `texlive-fonts-extra` (1.5 GB). If an equation needs a font from it, add it to the `apt-get` line in the Dockerfile. |
| Kokoro voice | Not shipped. To use it, put `kokoro-v1.0.onnx` and `voices-v1.0.bin` in `/data/workspace/models/` (Render Shell). |

## Try the image without Render

```bash
docker build -t lessonforge lessonforge
docker run -p 5000:5000 -e LESSONFORGE_ACCESS_TOKEN=pick-one -e OPENROUTER_API_KEY=... -v lf-data:/data lessonforge
# http://localhost:5000/app/?token=pick-one
```

The server refuses to start without `LESSONFORGE_ACCESS_TOKEN`, because it listens on a public address and
`/api/compile_video` runs posted Python.
