// Screenshots of the screens added on 2026-10-09, as a phone shows them. Presses nothing that spends or removes.
//   start     the history, with failed runs set aside
//   FAILED=<job id>   a failed run: "Remove this run", and "Edit the script" when it came from one
//   RUNNING=<job id>  a run in progress: "Stop and remove this run" (not pressed)
//   CONFIRM=1         walks the questions for one topic (the question model is called: about 0.02 USD; nothing on a
//                     server with no model key, which asks its fixed questions) to the read-back, and shows "How it
//                     is planned" as it opens (from sources first) and the other way. Prints the session id it made.
// Usage: APP_URL='https://…/app/?token=…' [FAILED=…] [RUNNING=…] [CONFIRM=1] [OUT=dir] node shot_ui.js [width height]
const puppeteer = require('puppeteer-core');
const fs = require('fs');

const APP_URL = process.env.APP_URL, OUT = process.env.OUT || 'out';
const WIDTH = parseInt(process.argv[2] || '390', 10), HEIGHT = parseInt(process.argv[3] || '844', 10);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
fs.mkdirSync(OUT, { recursive: true });

(async () => {
  const browser = await puppeteer.launch({ executablePath: process.env.CHROME || '/usr/bin/google-chrome', headless: 'new', args: ['--no-sandbox'] });
  const base = APP_URL.split('#')[0];
  // Each screen in a browser of its own: the app remembers the lesson last opened and would reopen it.
  const open = async (hash) => {
    const page = await (await browser.createBrowserContext()).newPage();
    await page.setViewport({ width: WIDTH, height: HEIGHT });
    await page.goto(base + (hash || ''), { waitUntil: 'networkidle2', timeout: 60000 });
    await sleep(2500);
    return page;
  };
  const text = (page) => page.evaluate(() => document.body.innerText);
  const bottom = (page) => page.evaluate(() => Array.from(document.querySelectorAll('div'))
    .filter((d) => d.scrollHeight > d.clientHeight + 40 && getComputedStyle(d).overflowY !== 'visible').forEach((d) => { d.scrollTop = d.scrollHeight; }));
  const to = (page, needle) => page.evaluate((needle) => {
    const el = Array.from(document.querySelectorAll('div')).filter((d) => (d.innerText || '').trim().startsWith(needle)).pop();
    if (el) el.scrollIntoView({ block: 'start' });
  }, needle);
  const report = (name, screen, needles) => console.log(`${name}: ` + needles.map((n) => `${screen.includes(n) ? '✓' : '✗'} ${n}`).join(' · '));

  let page = await open('');
  await bottom(page); await sleep(300);
  await page.screenshot({ path: `${OUT}/ui_start_${WIDTH}.png` });
  report('start', await text(page), ['Recent videos', 'hidden']);
  await page.close();

  if (process.env.FAILED) {
    page = await open(`#job=${process.env.FAILED}`);
    await to(page, 'Generation failed'); await sleep(300);
    await page.screenshot({ path: `${OUT}/ui_failed_${WIDTH}.png` });
    report('failed run', await text(page), ['Generation failed', 'Remove this run', 'Try again']);
    await page.close();
  }
  if (process.env.RUNNING) {
    page = await open(`#job=${process.env.RUNNING}`);
    await bottom(page); await sleep(300);
    await page.screenshot({ path: `${OUT}/ui_running_${WIDTH}.png` });
    report('run in progress', await text(page), ['Stop and remove this run', 'at its next step']);
    await page.close();
  }
  if (process.env.CONFIRM === '1') {
    page = await open('');
    let view = null;
    page.on('response', async (res) => { try { if (/\/api\/harness\/sessions/.test(res.url()) && res.request().method() === 'POST') view = await res.json(); } catch (e) { /* not JSON */ } });
    const next = async (act) => { view = null; await act(); const end = Date.now() + 45000; while (Date.now() < end && !view) await sleep(200); await sleep(400); return view; };
    const tap = async (label) => {
      const h = await page.evaluateHandle((label) => {
        const hits = Array.from(document.querySelectorAll('div')).filter((el) => (el.innerText || '').trim().startsWith(label));
        // The shortest match, and of several equally short the LAST on the page: an answer already given ("Skip")
        // stays in the conversation as a bubble with the same words as the button under it.
        const shortest = Math.min(...hits.map((el) => el.innerText.length));
        return hits.filter((el) => el.innerText.length === shortest).pop() || null;
      }, label);
      const el = h.asElement(); if (!el) return false;
      await el.evaluate((n) => n.scrollIntoView({ block: 'center' })); await el.click(); return true;
    };
    const type = async (value) => { await page.type('input[placeholder]', value, { delay: 2 }); await page.keyboard.press('Enter'); };
    let v = await next(() => type('Comparing fractions for class 6 in Hinglish, about 2 minutes'));
    for (let turn = 0; turn < 14 && v && v.question; turn++) {
      const q = v.question;
      if (q.options && q.options.length) v = await next(() => tap(q.options[0].label));
      else if (q.optional) v = await next(() => tap('Skip'));
      else v = await next(() => type(q.id === 'goal' ? 'say which of two fractions is bigger and why' : 'Class 6 students'));
    }
    console.log('session ' + (v && v.session_id));
    await to(page, 'How it is planned'); await sleep(300);
    // Planned from sources first unless the requester chooses otherwise (the owner, 2026-10-10): that is how it opens.
    await page.screenshot({ path: `${OUT}/ui_confirm_sources_${WIDTH}.png` });
    report('read-back, as it opens', await text(page), ['Here is what I will make', 'How it is planned', 'From sources first', 'From your answers only',
      'Reads the textbook chapter', 'Generate video']);
    await tap('From your answers only'); await sleep(400);
    await to(page, 'How it is planned'); await sleep(300);
    await page.screenshot({ path: `${OUT}/ui_confirm_answers_${WIDTH}.png` });
    report('read-back, answers only', await text(page), ['The script is written from what you answered above', 'Generate video']);
    await page.close();
  }
  await browser.close();
})().catch((e) => { console.error('driver crashed:', e); process.exit(2); });
