# Browser tests

Real-browser checks of the web client against a running server, normally through the
public link, because that is what a tester uses. They live here and not in a temp folder:
the temp folder was wiped by a reboot on 2026-10-08 and the drivers with it.

```bash
cd tests/browser && npm install          # once: puppeteer-core, driving the system Chrome
bash ../../scripts/public_link.sh        # prints the link; it is also in <workspace>/logs/tunnel.url
APP_URL='https://…/app/?token=…' node e2e_dashboard.js [width height]
```

| Script | What it does | Spends |
|---|---|---|
| `e2e_dashboard.js` | Opens `#dashboard`, opens a finished lesson from it, plays it through at 8×, checks the play and the watched share are counted, then leaves its own visits out | nothing |
| `e2e_watch.js` | On a finished lesson (`JOB=<id>`): an in-video question pauses it, answering continues, a shorter watch mode skips | nothing |
| `e2e.js` | The whole flow: intake, generate, playback, reload, history | **one lesson** (about 0.5 to 1 USD) |
| `e2e_script.js` | A video from a pasted script: "Use my script", the read-back, generate, playback, reload, "Edit the script and make it again", the history tag. `GENERATE=0` stops at the read-back | **one short lesson** (about 0.2 to 0.5 USD); nothing with `GENERATE=0` |
| `e2e_controls.js` | The "All controls" panel on a pasted script's read-back: every group the server lists, a toggle, a number, a model list and a choice changed, the count of changes, a per-row reset, and the settings the POST to `/generate` carries (the POST is intercepted and never sent) | nothing |
| `e2e_tryit.js` | "Try it yourself" on a finished lesson that has a task (`JOB=<id>`): the steps stay hidden until a guess is in, the expected answer appears only after an answer is sent, the owner reads it back, and with `REVIEW_TOKEN=<token>` a student sends one and cannot read the others | nothing |
| `e2e_voice.js` | "Add the voice" on a finished lesson that is silent or in the basic voice (`JOB=<id>`), or with `LABEL='Finish this lesson'` the button of a failed lesson whose script and pictures were kept: the new lesson is followed to its end and must play with sound decoded. With the spending cap reached it reports the refusal the app shows. `PRESS=0` only checks that the button is offered | **the narration of that lesson** (about 3 cents a minute); nothing with `PRESS=0` or when refused |
| `shot_ui.js` | Phone-size screenshots of the history (failed runs set aside), a failed run (`FAILED=<id>`), a run in progress (`RUNNING=<id>`) and, with `CONFIRM=1`, the read-back with "How it is planned". Presses nothing that spends or removes | nothing; about 0.02 USD with `CONFIRM=1` (the question model) |
| `shot_dashboard.js` | One tall screenshot of the dashboard as its owner sees it | nothing |
| `shot_intake.js` | Walks the intake conversation to its last question and screenshots the "kind of video" and "simple example" questions | about 0.01 USD (question model) |
| `check_fullscreen.js` | A viewer watching fullscreen still gets the question (`JOB=<id>`) | nothing |
| `contact_sheet.sh` | Frames of a lesson video on one sheet | nothing |

Headless Chrome announces itself, so the server marks everything these do as `test` and
the dashboard leaves it out. `…#dashboard&tests=1` shows a view that counts them, which
is how `e2e_dashboard.js` checks its own play. Nothing needs cleaning up afterwards.

A check that compares totals must allow for other people using the app at the same time
(`>=`, not `==`): the first run on a shared link failed because a real visitor pressed play.

Screenshots go to `out/` (git-ignored). The student-review driver was not recovered after
the reboot; `tests/unit/test_feedback.py` and `test_analytics.py` cover its server side.
