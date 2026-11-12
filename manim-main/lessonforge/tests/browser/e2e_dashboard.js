// Dashboard test in a real browser, against a running server (usually through the public link).
// Generates nothing, so it spends nothing:
//   open #dashboard → numbers load → open a finished lesson from it → play it through at speed →
//   back on the dashboard the play and the watched share are there → "leave my visits out" removes them.
// This browser is headless, so the server marks its events as tests; the page is opened with
// &tests=1 to see them, and the real numbers are untouched.
//
//   APP_URL='https://…/app/?token=…' [JOB=<job id>] [OUT=dir] node e2e_dashboard.js [width height]
const puppeteer = require('puppeteer-core');

const APP_URL = process.env.APP_URL, JOB = process.env.JOB || '', OUT = process.env.OUT || 'out';
const WIDTH = parseInt(process.argv[2] || '1180', 10), HEIGHT = parseInt(process.argv[3] || '900', 10);
const CHROME = process.env.CHROME || '/usr/bin/google-chrome';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const problems = [], log = (...a) => console.log(...a);
const fail = (msg) => { problems.push(msg); log('  ✗', msg); };
if (!APP_URL) { console.error('set APP_URL to the app link, token included'); process.exit(2); }
require('fs').mkdirSync(OUT, { recursive: true });

(async () => {
  const browser = await puppeteer.launch({ executablePath: CHROME, headless: 'new',
    args: ['--no-sandbox', '--autoplay-policy=no-user-gesture-required'] });
  const page = await browser.newPage();
  await page.setViewport({ width: WIDTH, height: HEIGHT });
  let stats = null; const sent = [];
  page.on('pageerror', (e) => fail('page error: ' + String(e).slice(0, 300)));
  page.on('console', (m) => { if (m.type() === 'error' && !/favicon/.test(m.text())) fail('console error: ' + m.text().slice(0, 300)); });
  page.on('request', (req) => { if (/\/api\/harness\/events$/.test(req.url())) { try { sent.push(JSON.parse(req.postData())); } catch (e) { /* ignore */ } } });
  page.on('response', async (res) => {
    const url = res.url();
    if (res.status() >= 400 && !/favicon/.test(url)) fail(`HTTP ${res.status()} ${url.replace(/token=[^&]+/, 'token=…').slice(0, 140)}`);
    try { if (/\/api\/harness\/stats/.test(url)) stats = await res.json(); } catch (e) { /* not JSON */ }
  });
  const shot = (name, full = true) => page.screenshot({ path: `${OUT}/${name}.png`, fullPage: full });
  const text = () => page.evaluate(() => document.body.innerText);
  const has = async (needle) => (await text()).toLowerCase().includes(needle.toLowerCase());   // labels may be upper-cased by style
  const waitText = async (needle, ms = 15000) => { const end = Date.now() + ms; while (Date.now() < end) { if (await has(needle)) return true; await sleep(200); } return false; };
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
  const freshStats = async (ms = 12000) => { stats = null; const end = Date.now() + ms; while (Date.now() < end && !stats) await sleep(200); return stats; };

  // 1. the dashboard opens from its link and counts this browser
  const url = APP_URL + '#dashboard&tests=1';
  log(`→ ${url.replace(/token=[^&#]+/, 'token=…')}  (${WIDTH}×${HEIGHT})`);
  await page.goto(url, { waitUntil: 'networkidle2', timeout: 60000 });
  if (!(await waitText('Lessons made'))) fail('the dashboard did not load its numbers');
  const first = stats;
  if (!first) fail('no /stats answer was seen');
  else {
    log('   totals: ' + JSON.stringify(first.totals));
    log('   spend: ' + JSON.stringify(first.spend) + ' | devices ' + JSON.stringify(first.devices) + ' | countries ' + JSON.stringify(first.countries));
    if (!first.me) fail('the server did not say which visitor this browser is');
    if (!first.visitors.some((v) => v.visitor === first.me)) fail('this browser is not among the visitors');
    if (first.totals.lessons < 1) fail('no lessons are listed');
    if (!(first.spend.spent > 0)) fail('spend is missing');
  }
  for (const needle of ['Dashboard', 'Visitors', 'Conversations', 'Video plays', 'Reviews', 'Spend', 'Each day', 'How far visitors get', 'Lessons', '(you)', 'counted here too'])
    if (!(await has(needle))) fail('the dashboard does not show "' + needle + '"');
  if (!page.url().includes('#dashboard')) fail('the address bar lost #dashboard: ' + page.url().replace(/token=[^&#]+/, 'token=…'));
  await shot('d1_dashboard');
  // the chart follows the chosen measure
  if (!(await clickText('Lessons made', true))) fail('no "Lessons made" chart chip');
  await sleep(300);
  await clickText('Spend', true); await sleep(300);
  await shot('d2_spend_chart');

  // 2. open a finished lesson from the dashboard and watch it through, fast
  const target = first && (first.lessons.find((l) => l.job_id === JOB) || first.lessons.find((l) => l.status === 'done'));
  if (!target) fail('no finished lesson to open');
  else {
    if (!(await clickText(target.title))) fail('could not tap the lesson "' + target.title + '"');
    const end = Date.now() + 20000;
    while (Date.now() < end && !(await page.$('video'))) await sleep(300);
    if (!(await page.$('video'))) fail('the lesson did not open from the dashboard');
    else {
      if (!page.url().includes('#job=' + target.job_id)) fail('the address bar does not carry the lesson: ' + page.url().replace(/token=[^&#]+/, 'token=…'));
      await sleep(1200);
      // Questions would stop the video; switch them off for an uninterrupted run.
      if (await has('Pause for questions')) { await clickText('Pause for questions', true); await sleep(300); }
      const length = await page.evaluate(() => new Promise((resolve) => {
        const v = document.querySelector('video'); v.muted = true; v.playbackRate = 8;
        const go = () => v.play().then(() => resolve(v.duration)).catch((e) => resolve(String(e)));
        if (v.readyState >= 1) go(); else v.addEventListener('loadedmetadata', go, { once: true });
      }));
      log(`   playing "${target.title}" (${Math.round(length)} s) at 8×`);
      const until = Date.now() + Math.min(150000, (Number(length) / 8) * 1000 * 1.6 + 15000);
      while (Date.now() < until && !sent.some((e) => e.event === 'progress' && e.value === 100)) {
        await sleep(1000);
        // a question that still appeared, or a stall: keep it moving
        await page.evaluate(() => { const v = document.querySelector('video'); if (v && v.paused && !v.ended) { v.playbackRate = 8; v.play().catch(() => {}); } else if (v) v.playbackRate = 8; });
        if (await has('Continue')) await clickText('Continue', true);
      }
      const reported = sent.filter((e) => e.event !== 'screen').map((e) => `${e.event}:${e.value}`);
      log('   reported by the player: ' + reported.join(' '));
      for (const want of ['play:full', 'progress:25', 'progress:50', 'progress:75', 'progress:100'])
        if (!reported.includes(want)) fail('the player did not report ' + want);
      if (reported.filter((r) => r.startsWith('play')).length !== 1) fail('"play" was reported more than once for one viewing');
      await page.evaluate(() => document.querySelector('video') && document.querySelector('video').pause());
    }
  }
  log('   screens reported: ' + sent.filter((e) => e.event === 'screen').map((e) => e.value).join(' → '));

  // 3. back to the dashboard by its header link (shown because this browser has opened it before)
  if (!(await clickText('New video', true))) fail('no "New video" button');
  await sleep(800);
  stats = null;
  if (!(await clickText('Dashboard', true))) fail('no "Dashboard" link in the header after the dashboard was opened once');
  const second = await freshStats();
  if (!(await waitText('Latest activity'))) fail('the dashboard did not come back');
  if (second && first && target) {
    const before = first.lessons.find((l) => l.job_id === target.job_id), after = second.lessons.find((l) => l.job_id === target.job_id);
    log(`   lesson before: plays ${before.plays}, half ${before.watched_half}, end ${before.watched_end} | after: plays ${after.plays}, half ${after.watched_half}, end ${after.watched_end}`);
    if (after.plays !== before.plays + 1) fail(`the play was not counted (plays ${before.plays} → ${after.plays})`);
    if (after.watched_end < 1 || after.watched_half < 1) fail('watching to the end was not counted');
    if (second.totals.plays < first.totals.plays + 1) fail("the plays total did not go up");   // others may be watching too
    const mine = second.visitors.find((v) => v.visitor === second.me);
    if (!mine || mine.plays < 1) fail('the play is not on this visitor');
    if (!second.recent.some((e) => e.event === 'progress' && e.value === 100 && e.job_id === target.job_id)) fail('"watched to the end" is not in the latest activity');
    const funnel = Object.fromEntries(second.funnel.map((s) => [s.id, s.visitors]));
    log('   funnel: ' + JSON.stringify(funnel));
    if (!(funnel.opened >= funnel.played && funnel.played >= 1 && funnel.watched >= 1)) fail('the funnel does not add up: ' + JSON.stringify(funnel));
  } else fail('no second /stats answer');
  if (!/watched “.+” to the end/.test(await text())) fail('the activity list does not say the lesson was watched to the end');
  if (!page.url().includes('tests=1')) fail('the test-browser view was dropped on the way back: ' + page.url().replace(/token=[^&#]+/, 'token=…'));
  await shot('d3_after_watch');

  // 4. leaving my own visits out removes this browser
  if (!(await clickText('Counting my own visits', true))) fail('no "Counting my own visits" switch');
  const third = await freshStats();
  if (!third) fail('no /stats answer after the switch');
  else if (third.visitors.some((v) => v.visitor === third.me) || (second && third.totals.visitors !== second.totals.visitors - 1)) fail('this browser is still counted after switching it off');
  if (!(await waitText('Leaving my own visits out', 4000))) fail('the switch did not change its label');
  await clickText('Counting my own visits', true).catch(() => {});
  await clickText('Leaving my own visits out', true); await freshStats();
  await clickText('Today', true); await freshStats();
  await sleep(400);
  await shot('d4_today');

  log(problems.length ? `\nFAILED with ${problems.length} problem(s):\n - ` + problems.join('\n - ') : '\nDASHBOARD E2E OK');
  await browser.close();
  process.exit(problems.length ? 1 : 0);
})().catch((e) => { console.error('driver crashed:', e); process.exit(2); });
