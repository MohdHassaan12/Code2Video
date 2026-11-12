// "Try it yourself" on a finished lesson that has a task, in a real browser. Spends nothing.
//   owner link:  the task under the video; the steps stay hidden until a guess is in; the expected
//                answer appears only after an answer is sent; the answer is kept and can be read back;
//                the teaching card is shown when the lesson has one.
//   review link: a student can do the task and send an answer, and cannot read the others'.
// Usage: APP_URL='https://…/app/?token=<owner>' JOB=<job id> [REVIEW_TOKEN=<review token>] [OUT=dir] node e2e_tryit.js [width height]
const puppeteer = require('puppeteer-core');
const fs = require('fs');

const APP_URL = process.env.APP_URL, JOB = process.env.JOB, REVIEW_TOKEN = process.env.REVIEW_TOKEN || '';
const OUT = process.env.OUT || 'out';
const WIDTH = parseInt(process.argv[2] || '390', 10), HEIGHT = parseInt(process.argv[3] || '844', 10);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const problems = [], log = (...a) => console.log(...a);
const fail = (msg) => { problems.push(msg); log('  ✗', msg); };
fs.mkdirSync(OUT, { recursive: true });

(async () => {
  const browser = await puppeteer.launch({ executablePath: process.env.CHROME || '/usr/bin/google-chrome', headless: 'new', args: ['--no-sandbox'] });
  const page = await browser.newPage();
  await page.setViewport({ width: WIDTH, height: HEIGHT });
  let job = null, stored = null;
  page.on('pageerror', (e) => fail('page error: ' + String(e).slice(0, 300)));
  page.on('response', async (res) => {
    try {
      const url = res.url();
      if (new RegExp(`/api/harness/jobs/${JOB}$`).test(url)) job = await res.json();
      if (/\/tryit$/.test(url) && res.request().method() === 'POST' && res.status() === 200) stored = await res.json();
    } catch (e) { /* not JSON */ }
  });
  const text = () => page.evaluate(() => document.body.innerText);
  // Section labels are drawn in capitals by a style, and innerText reports them that way.
  const has = (screen, needle) => screen.toLowerCase().includes(String(needle).toLowerCase());
  const waitText = async (needle, ms = 20000) => {
    const end = Date.now() + ms;
    while (Date.now() < end) { if ((await text()).includes(needle)) return true; await sleep(200); }
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
  const typeInto = async (placeholder, value) => {
    const box = await page.$(`input[placeholder="${placeholder}"], textarea[placeholder="${placeholder}"]`);
    if (!box) { fail(`no field "${placeholder}"`); return; }
    await box.evaluate((n) => n.scrollIntoView({ block: 'center' }));
    await box.click();
    await box.type(value, { delay: 2 });
  };
  const shotAt = async (needle, name) => {
    await page.evaluate((needle) => {
      const el = Array.from(document.querySelectorAll('div')).filter((d) => (d.innerText || '').trim().startsWith(needle)).pop();
      if (el) el.scrollIntoView({ block: 'start' });
    }, needle);
    await sleep(300);
    await page.screenshot({ path: `${OUT}/tryit_${name}_${WIDTH}.png` });
  };

  // ── the owner ──
  const base = APP_URL.split('#')[0];
  log(`→ owner  ${base.replace(/token=[^&#]+/, 'token=…')}#job=${JOB}  (${WIDTH}×${HEIGHT})`);
  await page.goto(`${base}#job=${JOB}`, { waitUntil: 'networkidle2', timeout: 60000 });
  if (!(await waitText('TRY IT YOURSELF', 30000))) { fail('no "Try it yourself" card on the watch screen'); throw new Error('cannot continue'); }
  const task = job && job.try_it;
  if (!task) { fail('the job record carries no try_it'); throw new Error('cannot continue'); }
  log(`   task: “${task.title}” · ${task.steps.length} steps · kind ${task.kind}`);
  let screen = await text();
  for (const needle of ['You need', task.materials[0], 'Guess first', task.predict, 'Lock in my guess']) {
    if (needle && !has(screen, needle)) fail(`before the guess, the card lacks: ${String(needle).slice(0, 50)}`);
  }
  if (screen.includes(task.steps[0])) fail('the steps are shown before a guess is in');
  if (screen.includes(task.expected)) fail('the expected answer is on screen before anything was answered');
  if (screen.includes('Check my answer')) fail('"Check my answer" is offered before the guess');
  await shotAt('TRY IT YOURSELF', '01_guess');
  await typeInto('My guess is…', 'the one cut into four');
  if (!(await clickText('Lock in my guess'))) fail('cannot lock the guess');
  await sleep(400);
  screen = await text();
  for (const needle of ['Your guess: the one cut into four', task.steps[0], task.steps[task.steps.length - 1], 'What did you see?', task.question]) {
    if (!has(screen, needle)) fail(`after the guess, the card lacks: ${needle.slice(0, 50)}`);
  }
  if (screen.includes(task.expected)) fail('the expected answer is shown before the learner answered');
  await typeInto('Say what happened, in your own words', 'the half was twice as big as the fourth');
  await typeInto('Because…', 'more parts of the same roti means each part is smaller');
  await shotAt('2 · Do it', '02_doing');
  if (!(await clickText('Check my answer'))) fail('no "Check my answer"');
  if (!(await waitText('Saved with this lesson', 15000))) fail('the answer was not saved');
  screen = await text();
  if (!stored || stored.count < 1) fail('the server did not confirm the stored answer');
  for (const needle of [task.expected, task.observe]) if (needle && !screen.includes(needle)) fail(`after checking, missing: ${needle.slice(0, 50)}`);
  // Other people may have answered on the same server: at least this one is counted.
  if (!/[1-9]\d* answers? so far\./.test(screen)) fail('the owner is not told how many answered');
  await shotAt('3 · What did you see?', '03_revealed');
  if (!(await clickText('Read them'))) fail('the owner cannot read the answers');
  if (!(await waitText('Guessed: the one cut into four', 8000))) fail('the stored answer does not come back');
  if (task.in_class) {
    await clickText('Doing this with a whole class?');
    await sleep(300);
    if (!(await text()).includes(task.in_class)) fail('the class version does not open');
  }
  if (job.card) {
    screen = await text();
    for (const needle of ['WHAT THIS LESSON STANDS ON', job.card.big_idea, job.card.the_why, (job.card.mistakes[0] || {}).mistake, (job.card.sources[0] || {}).title]) {
      if (needle && !screen.includes(needle)) fail(`the teaching card lacks: ${String(needle).slice(0, 50)}`);
    }
    if (/S\d#\d/.test(screen)) fail('a passage id is shown to the user');
    await shotAt('WHAT THIS LESSON STANDS ON', '04_card');
  } else log('   (this lesson has no teaching card)');
  const files = await page.evaluate(async (job) => {
    const code = async (path) => (await fetch(path)).status;
    return { pack: await code(`/lessons/${job}/teaching_pack.json`), answers: await code(`/lessons/${job}/tryit/`), lesson: await code(`/lessons/${job}/lesson.json`) };
  }, JOB);
  if (files.pack !== 404 || files.answers !== 404 || files.lesson !== 200) fail('private files of the lesson are served: ' + JSON.stringify(files));

  // ── a student, through a review link ──
  if (REVIEW_TOKEN) {
    const review = `${base.replace(/token=[^&#]+/, 'token=' + REVIEW_TOKEN)}#review=${JOB}`;
    log('→ student  (review link)');
    const student = await browser.newPage();
    await student.setViewport({ width: WIDTH, height: HEIGHT });
    let kept = null;
    student.on('response', async (res) => { try { if (/\/tryit$/.test(res.url()) && res.request().method() === 'POST') kept = { status: res.status(), body: await res.json() }; } catch (e) { /* */ } });
    await student.goto(review, { waitUntil: 'networkidle2', timeout: 60000 });
    const seen = async () => student.evaluate(() => document.body.innerText);
    const until = async (needle, ms = 20000) => { const end = Date.now() + ms; while (Date.now() < end) { if ((await seen()).includes(needle)) return true; await sleep(200); } return false; };
    const tap = async (label) => {
      const h = await student.evaluateHandle((label) => {
        const hits = Array.from(document.querySelectorAll('div, span')).filter((el) => (el.innerText || '').trim() === label);
        hits.sort((a, b) => a.querySelectorAll('*').length - b.querySelectorAll('*').length);
        return hits[0] || null;
      }, label);
      const el = h.asElement(); if (!el) return false;
      await el.evaluate((n) => n.scrollIntoView({ block: 'center' })); await el.click(); return true;
    };
    if (!(await until('TRY IT YOURSELF', 30000))) fail('the review screen has no "Try it yourself" card');
    if (!(await tap('I can’t guess'))) fail('a student cannot skip the guess');
    await sleep(300);
    const box = await student.$('textarea[placeholder="Because…"], input[placeholder="Because…"]');
    if (!box) fail('a student sees no answer field'); else { await box.evaluate((n) => n.scrollIntoView({ block: 'center' })); await box.click(); await box.type('each part gets smaller', { delay: 2 }); }
    if (!(await tap('Check my answer'))) fail('a student cannot check');
    let saved = await until('Saved with this lesson', 15000);
    if (!saved && (await seen()).includes('was not sent')) {
      // The request was dropped on the way (this happens to headless Chrome on a network that changes): the app
      // keeps what was written and says so, and a second press sends it.
      log('     (network blip: the app kept the answer and asked to try again)');
      await tap('Check my answer');
      saved = await until('Saved with this lesson', 15000);
    }
    if (!saved) fail('a student\'s answer was not saved: ' + JSON.stringify(kept));
    const after = await seen();
    if (/answers? so far|Read them/.test(after)) fail('a student is offered the other answers');
    const reach = await student.evaluate(async (job) => ({ others: (await fetch(`/api/harness/jobs/${job}/tryit`)).status, pack: (await fetch(`/lessons/${job}/teaching_pack.json`)).status }), JOB);
    if (reach.others !== 403 || reach.pack !== 404) fail('a review link reaches too much: ' + JSON.stringify(reach));
    await student.evaluate(() => { const el = Array.from(document.querySelectorAll('div')).filter((d) => (d.innerText || '').trim().startsWith('TRY IT YOURSELF')).pop(); if (el) el.scrollIntoView({ block: 'start' }); });
    await sleep(300);
    await student.screenshot({ path: `${OUT}/tryit_05_student_${WIDTH}.png` });
    if (saved) log('   student: answered and saved; cannot read the others');
  }
  log(problems.length ? `\nFAILED with ${problems.length} problem(s):\n - ` + problems.join('\n - ') : '\nE2E TRY-IT OK');
  await browser.close();
  process.exit(problems.length ? 1 : 0);
})().catch((e) => { console.error('driver crashed:', e); process.exit(2); });
