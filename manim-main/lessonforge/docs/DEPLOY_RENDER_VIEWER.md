# The lessons on Render: a fixed address for watching

Written 2026-10-15 for the owner's request of that day: serve the app and every finished lesson from Render at a
fixed address, while lessons keep being made on the GPU machine. Storage is Cloudflare: R2 for the lessons, D1 for
what viewers write.

```
GPU machine (studio: makes lessons)            Cloudflare                       Render (viewer: shows them)
  lessonforge serve  ── a lesson finishes ──►  R2 bucket                 ◄──── lessonforge.viewer (Docker)
  lessonforge publish --all                     lessons/<id>/… files            /app/  the same app, "viewer" mode
                                                api/jobs.json, api/jobs/<id>.json   /api/harness/jobs…  read from R2
                                               D1 database               ◄──── reviews, try-it answers, plays
                         a viewer's browser ◄── the video, by a signed link (never through Render)
```

- **Nothing is made on Render.** Every route that makes or changes a lesson answers 403 there ("Lessons are made on
  the studio server; this site shows the finished ones."), and the app hides those buttons when the server says it
  is a viewer (`GET /api/harness/mode`).
- **Render's disk keeps nothing.** A deploy or a restart loses nothing: the lessons are in R2, what viewers write is
  in D1.
- **What is published** is exactly what the studio's own `GET /api/harness/jobs` and `/jobs/{id}` return, and only the
  files a lesson's record points at (video, captions, the player's questions, the outline, the lesson, the review page
  and what it links to). Never the sources' text, reviews, try-it answers (`harness/gate.py`, `PRIVATE_IN_LESSON`),
  render caches, audio blocks or logs.

The code: `src/lessonforge/cloud.py` (R2 and D1), `src/lessonforge/harness/publish.py` (`lessonforge publish`),
`src/lessonforge/viewer.py` (the site), `deploy/Dockerfile`, and the Blueprint `deploy/render.yaml` (NOT the
`render.yaml` at the repository root: that one runs the whole studio on Render, `DEPLOY_RENDER.md`).

## 1. Cloudflare R2: a bucket and a key for it

1. In the Cloudflare dashboard: **R2 Object Storage → Create bucket**. Name it, for example, `lessonforge-lessons`.
   Leave public access **off**: the site hands out signed links that last six hours.
2. **R2 → Manage API tokens → Create API token**: permission **Object Read & Write**, limited to that bucket.
   Cloudflare then shows an **Access Key ID** and a **Secret Access Key** once: copy both.
3. Your **Account ID** is on the R2 overview page (and in the dashboard's address).
4. **The bucket needs one CORS rule**, because the web player loads the video with `crossOrigin="anonymous"`
   (`clients/lessonforge-app/src/Player.web.tsx`) and the site sends the browser to R2 for it. In the bucket:
   **Settings → CORS policy → Add**, with your Render address from step 4 (use `"*"` until you have it):

   ```json
   [
     {
       "AllowedOrigins": ["https://lessonforge-viewer.onrender.com"],
       "AllowedMethods": ["GET", "HEAD"],
       "AllowedHeaders": ["Range"],
       "ExposeHeaders": ["Content-Length", "Content-Range", "Accept-Ranges", "ETag"],
       "MaxAgeSeconds": 3600
     }
   ]
   ```

   Without it the page loads and the video stays black (the browser console says CORS). Captions, questions and the
   rest come through the site itself and need no rule.

You now have: `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_R2_BUCKET`, `CLOUDFLARE_R2_ACCESS_KEY_ID`,
`CLOUDFLARE_R2_SECRET_ACCESS_KEY`.

## 2. Cloudflare D1: a database and a token for it

1. **Storage & Databases → D1 → Create database**, for example `lessonforge-viewer`. Copy its **Database ID**.
   Create no tables: the site creates its three (`reviews`, `tryit`, `events`) the first time it needs them.
2. **My Profile → API Tokens → Create Token → Custom token**: permission **Account · D1 · Edit**, for your account.
   Copy the token. (The global API key works too: then set `CLOUDFLARE_EMAIL` and `CLOUDFLARE_API_KEY` instead of the
   token; add those two by hand in Render's Environment tab, the Blueprint does not list them.)

You now have: `CLOUDFLARE_D1_DATABASE_ID`, `CLOUDFLARE_API_TOKEN`.

## 3. On the GPU machine: publish what exists, then let new lessons publish themselves

1. Put the four R2 settings in `lessonforge/.env` (the D1 ones are only needed on Render):

   ```bash
   CLOUDFLARE_ACCOUNT_ID=...
   CLOUDFLARE_R2_BUCKET=lessonforge-lessons
   CLOUDFLARE_R2_ACCESS_KEY_ID=...
   CLOUDFLARE_R2_SECRET_ACCESS_KEY=...
   ```

2. Install the R2 client once: `.venv/bin/pip install -e ".[cloud]"` (that is boto3).
3. See what would be sent, then send it:

   ```bash
   .venv/bin/lessonforge publish --all --dry-run
   .venv/bin/lessonforge publish --all
   ```

   It prints each lesson and the megabytes sent. Running it again sends nothing that is already there; a lesson taken
   out of the history here is taken off the site by `--all`. One lesson: `lessonforge publish <job id>`.
4. **Restart the live server** (`bash scripts/public_link.sh --restart`, which refuses while a lesson is being made)
   so it reads the new `.env`. From then on a lesson that finishes publishes itself (its log ends with a
   `[publish]` line), and one removed in the app leaves the site. `LESSONFORGE_PUBLISH=0` in `.env` turns both off.
   A failed upload never touches the lesson: run `lessonforge publish --all` later.

## 4. On Render: the Blueprint

1. Merge this work into `main` of `ManideepDonkena/manim`.
2. Render dashboard → **New → Blueprint** → connect GitHub and give Render access to the private repository
   `ManideepDonkena/manim` → pick it and the `main` branch. In **Blueprint Path** enter
   `lessonforge/deploy/render.yaml` (left empty, Render reads the root `render.yaml`, which is the whole studio).
3. Render reads the file and asks for each secret (`sync: false`). Fill them in:

   | setting | value |
   |---|---|
   | `LESSONFORGE_ACCESS_TOKEN` | a long random string made of letters, digits, `-` and `_` only (it travels in the link, where a `+` would turn into a space): `python3 -c "import secrets; print(secrets.token_urlsafe(24))"`. Everyone you share the site with gets a link carrying it |
   | `LESSONFORGE_REVIEW_TOKEN` | optional: a second string for students' review-only links |
   | `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_R2_BUCKET`, `CLOUDFLARE_R2_ACCESS_KEY_ID`, `CLOUDFLARE_R2_SECRET_ACCESS_KEY` | from step 1 |
   | `CLOUDFLARE_D1_DATABASE_ID`, `CLOUDFLARE_API_TOKEN` | from step 2 |

4. **Apply**. The first build takes several minutes (it builds the web app, then a small Python image).
5. Open `https://<your service>.onrender.com/healthz`: it must say `"objects": "r2", "database": "d1", "missing": []`.
   A setting that is missing is named there, and in the 503 the app would show.
6. Open `https://<your service>.onrender.com/app/?token=<LESSONFORGE_ACCESS_TOKEN>`: the list of lessons. The token
   is remembered by that browser; share the same link. Put the address into the R2 CORS rule (step 1.4).

The list is read from R2 at most once a minute, so a lesson published a moment ago shows within a minute.

## 5. What it costs

Figures only as read on the providers' own pages, with the date; anything else is on their pricing pages.

- **Render** (read 2026-10-15 at https://render.com/docs/free): a Free web service is spun down after 15 minutes
  without a request, and the next request waits while it starts again ("about one minute"); each workspace gets 750
  Free instance hours a calendar month. A paid instance type removes the Free limits; `plan: starter` in
  `deploy/render.yaml` (or the dashboard) is the smallest. Its price: https://render.com/pricing.
- **Cloudflare R2** (storage, operations, egress) and **Cloudflare D1** (rows read and written, storage): see
  https://developers.cloudflare.com/r2/pricing/ and https://developers.cloudflare.com/d1/platform/pricing/. These were
  not read for this guide. What the site uses: R2 stores every published lesson's files (the videos of the last
  fourteen lessons on the GPU machine were 5 to 16 MB each, most about 8 to 9 MB; the other files of a lesson are a
  few hundred kilobytes) and serves each play; D1 gets one row per review, try-it answer and counted event, and the
  Dashboard reads up to the newest 50,000 events when it is opened.
- Nothing on Render calls a model or a voice: no OpenRouter spend comes from the site.

## 6. What does not happen on Render

- **No lesson is made, narrated again, cut, repaired or removed there.** Those stay on the studio.
- **Reviews, try-it answers and plays written on Render stay in D1.** They are not yet copied back to the GPU
  machine: the studio's dashboard and `lessonforge feedback` do not see them, and the site's own Dashboard
  (`/app/?token=…#dashboard`) shows only the site's visitors, plays and reviews, with no spend. A copy back is not
  built.
- **Removing a lesson** on the studio takes it off the site at once (when publishing is on); nothing else edits R2.
- The site has no workspace: a lesson's `job.json`, its sources, its renders and its logs exist only on the GPU machine.

## 7. Trying it on this machine, without Cloudflare

`LESSONFORGE_CLOUD_DIR` makes a folder stand in for both: objects as files under `<dir>/r2/`, the database as
`<dir>/d1.sqlite3` running the same SQL. Never point it at the live workspace.

```bash
export LESSONFORGE_HOME=/tmp/trial/home         # a COPY of one or two finished lessons in lessons/
export LESSONFORGE_CLOUD_DIR=/tmp/trial/cloud
.venv/bin/lessonforge publish --all
LESSONFORGE_WEB_APP=clients/lessonforge-app/dist .venv/bin/uvicorn lessonforge.viewer:app --port 5070
# or the real image (rootless podman works on this machine; docker needs root here):
podman build -f lessonforge/deploy/Dockerfile -t lessonforge-viewer .        # from the repository root
podman run --rm -p 5070:10000 -e LESSONFORGE_CLOUD_DIR=/cloud -v /tmp/trial/cloud:/cloud:Z lessonforge-viewer
```

Then `http://localhost:5070/healthz`, `/api/harness/jobs`, `/app/`. Tests: `tests/unit/test_viewer.py`.

## 8. When something is wrong

| what you see | why, and what to do |
|---|---|
| `/healthz` lists settings under `missing` | that setting is not in Render's Environment tab; add it and redeploy |
| the list is empty | nothing was published (step 3), or it was published less than a minute ago |
| the page loads, the video stays black | the R2 CORS rule (step 1.4) is missing or names another address |
| 401 everywhere | the link has no `?token=`, or the token differs from `LESSONFORGE_ACCESS_TOKEN` on Render |
| 502 "the lesson store did not answer" | R2 refused or was unreachable; check the R2 keys and the bucket name |
| a new lesson did not appear | its log on the studio ends with `[publish] skipped: …` and the reason; `lessonforge publish <id>` |
