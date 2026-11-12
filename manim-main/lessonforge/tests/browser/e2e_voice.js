// "Add the voice" in a real browser, through the public URL: a finished lesson that is silent (or in the
// basic voice) shows the button; pressing it starts a NEW lesson from the same script and pictures, which is
// followed to its end and must play WITH sound.
// Usage: APP_URL='https://…/app/?token=…' JOB=<id of a silent lesson> [PRESS=0] [OUT=dir] node e2e_voice.js [width height]
//   PRESS=0 stops once the button is on screen: nothing is started and nothing is spent.
//   Pressing it costs the narration of that lesson (about 3 cents a minute). A 402 answer (the spending cap or
//   the account cannot pay) is reported as what the app showed, not as a failure of the app.
const puppeteer = require('puppeteer-core');
const fs = require('fs');

const APP_URL = process.env.APP_URL, JOB = process.env.JOB, OUT = process.env.OUT || 'out';
const PRESS = process.env.PRESS !== '0';
// The button's words: 'Add the voice' on a finished silent lesson, 'Finish this lesson' on a failed one whose
// script and pictures were kept.
const LABEL = process.env.LABEL || 'Add the voice';
const WIDTH = parseInt(process.argv[2] || '390', 10), HEIGHT = parseInt(process.argv[3] || '844', 10);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const problems = [], log = (...a) => console.log(...a);
const fail = (msg) => { problems.push(msg); log('  ✗', msg); };
fs.mkdirSync(OUT, { recursive: true });

(async () => {
  if (!APP_URL || !JOB) { console.error('APP_URL and JOB are needed'); process.exit(2); }
  const browser = await puppeteer.launch({ executablePath: process.env.CHROME || '/usr/bin/google-chrome', headless: 'new',
    args: ['--no-sandbox', '--autoplay-policy=no-user-gesture-required'] });
  const page = await browser.newPage();
  await page.setViewport({ width: WIDTH, height: HEIGHT });
  let started = null, refusal = null, job = null, lastStage = '';
  page.on('pageerror', (e) => fail('page error: ' + String(e).slice(0, 300)));
  page.on('response', async (res) => {
    const url = res.url();
    try {
      if (/\/api\/harness\/jobs\/[^/]+\/voice/.test(url) && res.request().method() === 'POST') {
        if (res.status() >= 400) refusal = { status: res.status(), body: await res.text() };
        else started = await res.json();
        return;
      }
      if (/\/api\/harness\/jobs\/[^/?]+(\?|$)/.test(url) && res.request().method() === 'GET') {
        const j = await res.json();
        // Only a record with a status is a job; only the NEW lesson's record is followed.
        if (j && j.job_id && j.status && started && j.job_id === started.job_id) {
          job = j;
          if (j.stage !== lastStage) { lastStage = j.stage; log(`     new lesson ${j.job_id}: ${j.status} / ${j.stage}`); }
        }
      }
    } catch (e) { /* not JSON */ }
  });
  const text = () => page.evaluate(() => document.body.innerText);
  const waitText = async (needle, ms = 30000) => {
    const end = Date.now() + ms;
    while (Date.now() < end) { if ((await text()).includes(needle)) return true; await sleep(250); }
    return false;
  };
  const clickText = async (label) => {
    const handle = await page.evaluateHandle((label) => {
      const hits = Array.from(document.querySelectorAll('div, span, button')).filter((el) => (el.innerText || '').trim() === label);
      hits.sort((a, b) => a.querySelectorAll('*').length - b.querySelectorAll('*').length);
      return hits[0] || null;
    }, label);
    const el = handle.asElement();
    if (!el) return false;
    await el.evaluate((n) => n.scrollIntoView({ block: 'center' }));
    await el.click();
    return true;
  };
  const shot = (name) => page.screenshot({ path: `${OUT}/voice_${name}_${WIDTH}.png` });

  const base = APP_URL.split('#')[0];
  log(`→ ${base.replace(/token=[^&]+/, 'token=…')}#job=${JOB}  (${WIDTH}×${HEIGHT})`);
  await page.goto(`${base}#job=${JOB}`, { waitUntil: 'networkidle2', timeout: 60000 });
  if (!(await waitText(LABEL, 30000))) { fail(`the lesson does not offer "${LABEL}"`); }
  else {
    const screen = await text();
    log('   the lesson says: ' + (screen.split('\n').find((l) => /silent|basic voice|Generation failed/.test(l)) || '(no line about its state)').slice(0, 200));
    if (!/Nothing is planned or drawn again|keeps the script and the pictures/.test(screen)) fail('the screen does not say what the button does');
    await shot('01_offered');
    if (PRESS) await clickText(LABEL);
  }
  if (!PRESS || problems.length) {
    await browser.close();
    log(problems.length ? `\nFAILED with ${problems.length} problem(s):\n - ` + problems.join('\n - ') : '\nTHE BUTTON IS OFFERED (not followed: PRESS=0)');
    process.exit(problems.length ? 1 : 0);
  }

  // The click above was the press. Wait for the server's answer to it.
  const end = Date.now() + 30000;
  while (Date.now() < end && !started && !refusal) await sleep(200);
  if (refusal) {
    await sleep(800);
    await shot('02_refused');
    const shown = (await text()).split('\n').find((l) => /spending cap|credit|could not/i.test(l)) || '';
    log(`   refused (${refusal.status}): ${refusal.body.slice(0, 260)}`);
    if (!shown) fail('the app did not show why the voice could not be added');
    else log('   the app shows: ' + shown.slice(0, 220));
    await browser.close();
    log(problems.length ? `\nFAILED with ${problems.length} problem(s):\n - ` + problems.join('\n - ') : '\nREFUSED, AND THE APP SAYS WHY (nothing was started)');
    process.exit(problems.length ? 1 : 0);
  }
  if (!started) { fail('no answer to the press within 30 s'); await browser.close(); process.exit(1); }
  log(`   started: ${started.job_id} (from ${started.brief && started.brief.voice_for})`);
  if (started.job_id === JOB) fail('the same lesson came back: a new one was expected');
  const deadline = Date.now() + 40 * 60 * 1000;
  while (Date.now() < deadline && !(job && (job.status === 'done' || job.status === 'failed'))) await sleep(2000);
  await sleep(2500);
  await shot('03_finished');
  if (!job || job.status !== 'done') fail(`the new lesson did not finish: ${job && job.status} ${job && job.error}`);
  else {
    log(`   voice: ${String(job.voice).split('|')[0]} · alignment ${JSON.stringify(job.alignment && { clips: job.alignment.clips, trusted: job.alignment.trusted })}`);
    if (job.voice === 'silent' || String(job.voice).startsWith('gtts')) fail('the new lesson has no real narration either: ' + job.voice);
    if ((await text()).includes('Add the voice')) fail('the new lesson still offers "Add the voice"');   // it has its voice now
    const info = await page.evaluate(async () => {
      const v = document.querySelector('video');
      if (!v) return { error: 'no video element' };
      v.muted = true;
      await new Promise((res) => { if (v.readyState >= 2) return res(); v.addEventListener('loadeddata', res, { once: true }); setTimeout(res, 20000); });
      try { await v.play(); } catch (e) { return { error: String(e) }; }
      await new Promise((r) => setTimeout(r, 5000));
      v.pause();
      return { duration: v.duration, currentTime: v.currentTime, audioBytes: v.webkitAudioDecodedByteCount || 0, tracks: v.textTracks.length };
    });
    log('   video: ' + JSON.stringify(info));
    if (info.error || !(info.currentTime > 1)) fail('the new video did not play: ' + JSON.stringify(info));
    else if (!(info.audioBytes > 1000)) fail('the new video played without sound being decoded: ' + JSON.stringify(info));
  }
  await browser.close();
  log(problems.length ? `\nFAILED with ${problems.length} problem(s):\n - ` + problems.join('\n - ') : '\nE2E VOICE OK');
  if (started) log('JOB ' + started.job_id);
  process.exit(problems.length ? 1 : 0);
})().catch((e) => { console.error('driver crashed:', e); process.exit(2); });
