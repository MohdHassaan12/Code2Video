// Watch-screen test in a real browser through the public URL, on an EXISTING finished lesson:
// video plays → an in-video question pauses it → answering continues → a shorter watch mode skips ahead.
// Usage: APP_URL=https://…/app/?token=… JOB=<job id> OUT=/dir node e2e_watch.js [width height]
const puppeteer = require('puppeteer-core');

const APP_URL = process.env.APP_URL, JOB = process.env.JOB, OUT = process.env.OUT || '.';
const WIDTH = parseInt(process.argv[2] || '1180', 10), HEIGHT = parseInt(process.argv[3] || '900', 10);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const problems = [], log = (...a) => console.log(...a);
const fail = (msg) => { problems.push(msg); log('  ✗', msg); };

(async () => {
  const browser = await puppeteer.launch({ executablePath: '/usr/bin/google-chrome', headless: 'new',
    args: ['--no-sandbox', '--autoplay-policy=no-user-gesture-required'] });
  const page = await browser.newPage();
  await page.setViewport({ width: WIDTH, height: HEIGHT });
  let job = null, interactions = null;
  page.on('pageerror', (e) => fail('page error: ' + String(e).slice(0, 300)));
  page.on('console', (m) => { if (m.type() === 'error' && !/favicon/.test(m.text())) fail('console error: ' + m.text().slice(0, 300)); });
  page.on('response', async (res) => {
    const url = res.url();
    if (res.status() >= 400 && !/favicon/.test(url)) fail(`HTTP ${res.status()} ${url.replace(/token=[^&]+/, 'token=…').slice(0, 140)}`);
    try {
      if (/\/api\/harness\/jobs\//.test(url) && res.request().method() === 'GET') { const j = await res.json(); if (j.job_id) job = j; }
      if (/interactions\.json/.test(url)) interactions = await res.json();
    } catch (e) { /* not JSON */ }
  });
  const shot = (name) => page.screenshot({ path: `${OUT}/${name}.png` });
  const text = () => page.evaluate(() => document.body.innerText);
  const waitText = async (needle, ms = 15000) => { const end = Date.now() + ms; while (Date.now() < end) { if ((await text()).includes(needle)) return true; await sleep(200); } return false; };
  const clickText = async (label, exact = false) => {
    const handle = await page.evaluateHandle((label, exact) => {
      const all = Array.from(document.querySelectorAll('div, span, button'));
      let hits = all.filter((el) => (el.innerText || '').trim() === label);
      if (!hits.length && !exact) hits = all.filter((el) => (el.innerText || '').trim().startsWith(label));
      hits.sort((a, b) => a.innerText.length - b.innerText.length || b.querySelectorAll('*').length - a.querySelectorAll('*').length);
      return hits[0] || null;
    }, label, exact);
    const el = handle.asElement();
    if (!el) return false;
    await el.evaluate((n) => n.scrollIntoView({ block: 'center' }));
    await el.click();
    return true;
  };
  const video = (fn, arg) => page.evaluate(new Function('arg', `const v = document.querySelector('video'); if (!v) return null; ${fn}`), arg);

  const url = APP_URL + '#job=' + JOB;
  log(`→ ${url.replace(/token=[^&#]+/, 'token=…')}  (${WIDTH}×${HEIGHT})`);
  await page.goto(url, { waitUntil: 'networkidle2', timeout: 60000 });
  const end = Date.now() + 20000;
  while (Date.now() < end && !(await page.$('video'))) await sleep(300);
  if (!(await page.$('video'))) { fail('the lesson did not open from its link'); await shot('w0_failed'); }
  await sleep(1500);
  await shot('w1_open');
  log('   lesson: ' + (job && job.title) + ' | cuts: ' + JSON.stringify(job && (job.cuts || []).map((c) => [c.id, c.seconds])) + ' | interactions: ' + (interactions && interactions.interactions.length));

  // 1. an in-video question pauses the lesson
  const first = interactions && interactions.interactions[0];
  if (!first) fail('no interactions were loaded for this lesson');
  else {
    await video('v.muted = true; v.currentTime = arg; return v.play().then(() => true).catch((e) => String(e));', Math.max(0, first.t - 2.5));
    if (!(await waitText('Your turn', 12000)) && !(await waitText('YOUR TURN', 500))) fail('the question overlay did not appear at t=' + first.t);
    await sleep(600);
    const paused = await video('return v.paused;');
    if (paused !== true) fail('the video was not paused for the question');
    if (!(await text()).includes(first.prompt.text.slice(0, 30))) fail('the question text is not shown: ' + first.prompt.text);
    await shot('w2_question');
    if (first.options && first.options.length) {
      const right = first.options.find((o) => o.correct) || first.options[0];
      if (!(await clickText(right.text))) fail('could not tap the option "' + right.text + '"');
      await sleep(700);
      if (!/Correct|✓/.test(await text())) fail('no "Correct" feedback after tapping the right option');
      await shot('w3_answered');
    } else if (!(await clickText('Show answer'))) fail('no "Show answer" button');
    await sleep(400);
    if (!(await clickText('Continue'))) fail('no "Continue" button');
    await sleep(2500);
    const after = await video('return {paused: v.paused, t: v.currentTime};');
    log('   after Continue: ' + JSON.stringify(after) + (first.resume_at ? ' (resume_at ' + first.resume_at + ')' : ''));
    if (!after || after.paused) fail('playback did not resume after Continue');
    if (first.resume_at && after && after.t < first.resume_at - 0.5) fail('playback did not skip the silent pause (expected ≥ ' + first.resume_at + ')');
    if (!/of \d+ correct|\d+ of \d+/.test(await text())) fail('no running score on the watch screen');
  }

  // 2. a shorter watch mode skips what it leaves out
  const cuts = (job && job.cuts) || [];
  const short = cuts.find((c) => c.id === 'revision') || cuts.find((c) => c.id !== 'full');
  if (!short) log('   (this lesson offers only the full version — watch modes not exercised)');
  else {
    await video('v.pause(); v.currentTime = 0; return true;');
    await sleep(500);
    if (!(await clickText(short.label))) fail('no "' + short.label + '" chip');
    await sleep(800);
    await video('v.muted = true; return v.play().then(() => true).catch((e) => String(e));');
    await sleep(2500);
    const t = await video('return v.currentTime;');
    const inside = short.ranges.some(([a, b]) => t >= a - 0.4 && t <= b + 0.4);
    log(`   ${short.label}: now at ${t && t.toFixed(1)}s, kept ranges ${JSON.stringify(short.ranges.slice(0, 4))}`);
    if (!inside) fail(`in "${short.label}" the player is at ${t}s, outside every kept range`);
    // jump into a skipped stretch: the player must move on to the next kept range
    const gap = short.ranges.length > 1 ? (short.ranges[0][1] + short.ranges[1][0]) / 2 : null;
    if (gap !== null && short.ranges[1][0] - short.ranges[0][1] > 3) {
      await video('v.currentTime = arg; return true;', gap);
      await sleep(2500);
      const t2 = await video('return v.currentTime;');
      if (!(t2 >= short.ranges[1][0] - 0.5)) fail(`a skipped stretch was played (at ${t2}s, next kept range starts ${short.ranges[1][0]}s)`);
      else log(`   skipped stretch: jumped to ${t2.toFixed(1)}s`);
    }
    await video('v.pause(); return true;');
    await shot('w4_mode');
  }
  log(problems.length ? `\nFAILED with ${problems.length} problem(s):\n - ` + problems.join('\n - ') : '\nWATCH E2E OK');
  await browser.close();
  process.exit(problems.length ? 1 : 0);
})().catch((e) => { console.error('driver crashed:', e); process.exit(2); });
