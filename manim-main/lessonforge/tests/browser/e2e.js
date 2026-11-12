// End-to-end test of the lessonforge web client in a real browser, through the public URL:
// intake conversation → confirm → generate → watch (video plays) → reload resumes → history lists it.
// Usage: APP_URL=https://…/app/?token=… OUT=/dir node e2e.js "topic sentence" [width height]
const puppeteer = require('puppeteer-core');

const APP_URL = process.env.APP_URL;
const OUT = process.env.OUT || '.';
const TOPIC = process.argv[2] || 'Area of a circle';
const WIDTH = parseInt(process.argv[3] || '1180', 10), HEIGHT = parseInt(process.argv[4] || '860', 10);
const PREFER = { duration_minutes: 'About 2 minutes', language: 'English', style: 'Crisp tutor' };
const TYPED = { audience: 'Class 7 students in a government school', goal: 'they should do problems on it' };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const problems = [], log = (...a) => console.log(...a);
const fail = (msg) => { problems.push(msg); log('  ✗', msg); };

(async () => {
  const browser = await puppeteer.launch({ executablePath: '/usr/bin/google-chrome', headless: 'new',
    args: ['--no-sandbox', '--autoplay-policy=no-user-gesture-required'] });
  const page = await browser.newPage();
  await page.setViewport({ width: WIDTH, height: HEIGHT });
  let view = null, job = null, lastStage = '';
  page.on('pageerror', (e) => fail('page error: ' + String(e).slice(0, 300)));
  page.on('console', (m) => { if (m.type() === 'error' && !/favicon/.test(m.text())) fail('console error: ' + m.text().slice(0, 300)); });
  page.on('requestfailed', (r) => { if (!/favicon|\.mp4/.test(r.url())) fail('request failed: ' + r.url().slice(0, 120) + ' ' + (r.failure() || {}).errorText); });
  page.on('response', async (res) => {
    const url = res.url();
    if (res.status() >= 400 && !/favicon/.test(url)) fail(`HTTP ${res.status()} ${url.replace(/token=[^&]+/, 'token=…').slice(0, 140)}`);
    try {
      if (/\/api\/harness\/sessions/.test(url) && res.request().method() !== 'OPTIONS') view = await res.json();
      if (/\/api\/harness\/(jobs\/|generate|sessions\/[0-9a-f]+\/generate)/.test(url)) {
        const j = await res.json();
        if (j && j.job_id) { job = j; if (j.stage !== lastStage) { lastStage = j.stage; log(`     job ${j.job_id}: ${j.status} / ${j.stage}`); } }
      }
    } catch (e) { /* not JSON */ }
  });
  const shot = async (name) => { await page.screenshot({ path: `${OUT}/${name}.png` }); };
  const text = () => page.evaluate(() => document.body.innerText);
  const waitText = async (needle, ms = 30000) => {
    const end = Date.now() + ms;
    while (Date.now() < end) { if ((await text()).includes(needle)) return true; await sleep(250); }
    return false;
  };
  const clickText = async (label) => {
    const handle = await page.evaluateHandle((label) => {
      const all = Array.from(document.querySelectorAll('div, span, button'));
      const hits = all.filter((el) => (el.innerText || '').trim() === label);
      const starts = hits.length ? hits : all.filter((el) => (el.innerText || '').trim().startsWith(label));
      starts.sort((a, b) => a.innerText.length - b.innerText.length || b.querySelectorAll('*').length - a.querySelectorAll('*').length);
      return starts[0] || null;
    }, label);
    const el = handle.asElement();
    if (!el) return false;
    await el.evaluate((n) => n.scrollIntoView({ block: 'center' }));
    await el.click();
    return true;
  };
  const type = async (value) => {
    const input = await page.$('input[placeholder], textarea[placeholder]');
    if (!input) { fail('no text composer on screen'); return; }
    await input.click({ clickCount: 3 });
    await input.type(value, { delay: 5 });
    await page.keyboard.press('Enter');
  };

  log(`→ ${APP_URL.replace(/token=[^&]+/, 'token=…')}  (${WIDTH}×${HEIGHT})`);
  await page.goto(APP_URL, { waitUntil: 'networkidle2', timeout: 60000 });
  if (!(await waitText('Make a lesson video', 20000))) fail('start screen did not render');
  await shot('01_start');
  log(`> ${TOPIC}`);
  let before = view;
  await type(TOPIC);

  const asked = [];
  for (let turn = 0; turn < 20; turn++) {
    const end = Date.now() + 40000;
    while (Date.now() < end && (view === before || (await text()).includes('Thinking…'))) await sleep(200);
    if (view === before) { fail('no answer from the server within 40 s'); break; }
    const q = view.question;
    if (view.note && !(await waitText(view.note.slice(0, 40), 4000))) fail('note not shown: ' + view.note.slice(0, 60));
    if (!q) break;
    asked.push(q.id);
    if (!(await waitText(q.prompt.slice(0, 50), 6000))) fail(`question "${q.id}" not on screen: ${q.prompt.slice(0, 60)}`);
    log(`   [${q.id}|${q.kind}|${q.source}] ${q.prompt}`);
    for (const o of q.options) {
      log(`        • ${o.label}${o.hint ? '  — ' + o.hint : ''}`);
      if (!(await text()).includes(String(o.label).slice(0, 30))) fail(`option not shown for ${q.id}: ${o.label}`);
    }
    if (turn === 1 || q.id === 'goal' || q.id === 'context') await shot(`02_question_${asked.length}_${q.id}`);
    before = view;
    const seenBefore = asked.filter((id) => id === q.id).length > 1;
    if (TYPED[q.id] && !seenBefore) { log(`> ${TYPED[q.id]}  (typed)`); await type(TYPED[q.id]); continue; }
    if (q.id === 'misconception') { log('> You decide  (typed)'); await type('You decide'); continue; }
    if (q.options.length) {
      const want = PREFER[q.id];
      const option = q.options.find((o) => want && String(o.label).startsWith(want)) || q.options[0];
      log(`> ${option.label}  (tapped)`);
      if (!(await clickText(String(option.label)))) fail(`could not tap option "${option.label}"`);
    } else { log('> skip'); if (!(await clickText('Skip'))) await type('a village cricket ground'); }
  }
  if (!(await waitText('Here is what I will make', 15000))) fail('confirm screen did not appear');
  await shot('03_confirm');
  log('   brief: ' + JSON.stringify(view && view.brief));
  await clickText('Draft · 480p');
  if (!(await clickText('Generate video'))) fail('no Generate button');
  await sleep(2500);
  await shot('04_making');
  const deadline = Date.now() + 20 * 60 * 1000;
  let shots = 0;
  while (Date.now() < deadline) {
    if (await page.$('video')) break;
    if ((await text()).includes('Generation failed')) break;
    if (job && job.stage === 'render' && shots === 0) { shots = 1; await shot('05_making_render'); }
    await sleep(2000);
  }
  if (!job || job.status !== 'done') fail(`job did not finish: ${job && job.status} ${job && job.error}`);
  await sleep(1500);
  const video = await page.$('video');
  if (!video) { fail('no <video> element on the result screen'); }
  else {
    const info = await page.evaluate(async () => {
      const v = document.querySelector('video');
      v.muted = true;
      const ready = () => new Promise((res) => { if (v.readyState >= 2) return res(); v.addEventListener('loadeddata', res, { once: true }); setTimeout(res, 20000); });
      await ready();
      try { await v.play(); } catch (e) { return { error: String(e), readyState: v.readyState, src: v.currentSrc }; }
      await new Promise((r) => setTimeout(r, 4000));
      v.pause();
      return { readyState: v.readyState, duration: v.duration, currentTime: v.currentTime, width: v.videoWidth, height: v.videoHeight,
               tracks: v.textTracks.length, src: v.currentSrc.replace(/token=[^&]+/, 'token=…'), error: v.error && v.error.message };
    });
    log('   video: ' + JSON.stringify(info));
    if (!(info.readyState >= 2 && info.duration > 5 && info.currentTime > 1)) fail('the video did not play: ' + JSON.stringify(info));
    if (!info.tracks) fail('no caption track on the video');
  }
  const body = await text();
  for (const needle of ['Script check', 'New video']) if (!body.includes(needle)) fail(`result screen lacks "${needle}"`);
  await shot('06_watch');
  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
  await page.evaluate(() => { const s = Array.from(document.querySelectorAll('div')).filter((d) => d.scrollHeight > d.clientHeight + 40 && getComputedStyle(d).overflowY !== 'visible'); s.forEach((d) => { d.scrollTop = d.scrollHeight; }); });
  await sleep(400);
  await shot('07_watch_cards');

  // A reload must come back to the same lesson (the job id is remembered).
  await page.reload({ waitUntil: 'networkidle2' });
  await sleep(2500);
  if (!(await page.$('video'))) fail('after a reload the lesson was not reopened'); else log('   reload: lesson reopened');
  await shot('08_after_reload');
  // "New video" → start screen with the history.
  if (!(await clickText('New video'))) fail('no "New video" button');
  await sleep(2500);
  const start = await text();
  if (!start.includes('Recent videos')) fail('start screen has no "Recent videos"');
  if (job && job.title && !start.includes(job.title.slice(0, 20))) fail('the new lesson is not in the history: ' + job.title);
  await shot('09_history');
  log(`\nasked: ${asked.join(' → ')}`);
  log(problems.length ? `\nFAILED with ${problems.length} problem(s):\n - ` + problems.join('\n - ') : '\nE2E OK');
  log('JOB ' + (job ? job.job_id : 'none'));
  await browser.close();
  process.exit(problems.length ? 1 : 0);
})().catch((e) => { console.error('driver crashed:', e); process.exit(2); });
