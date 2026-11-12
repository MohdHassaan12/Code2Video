// The intake conversation in a real browser, up to the last question — nothing is generated.
// Screenshots the "kind of video" and "simple example" questions as a requester sees them.
//   APP_URL='https://…/app/?token=…' [OUT=dir] node shot_intake.js "topic sentence" [width height]
const puppeteer = require('puppeteer-core');
const APP_URL = process.env.APP_URL, OUT = process.env.OUT || 'out';
const TOPIC = process.argv[2] || 'Square numbers for class 8 in Hinglish, about 6 minutes';
const WIDTH = parseInt(process.argv[3] || '390', 10), HEIGHT = parseInt(process.argv[4] || '844', 10);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
require('fs').mkdirSync(OUT, { recursive: true });
(async () => {
  const browser = await puppeteer.launch({ executablePath: process.env.CHROME || '/usr/bin/google-chrome', headless: 'new', args: ['--no-sandbox'] });
  const page = await browser.newPage();
  await page.setViewport({ width: WIDTH, height: HEIGHT });
  let view = null;
  page.on('response', async (res) => { try { if (/\/api\/harness\/sessions/.test(res.url()) && res.request().method() === 'POST') view = await res.json(); } catch (e) { /* not JSON */ } });
  const next = async (act) => { view = null; await act(); const end = Date.now() + 40000; while (Date.now() < end && !view) await sleep(200); await sleep(500); return view; };
  const tap = async (label) => {
    const h = await page.evaluateHandle((label) => {
      const hits = Array.from(document.querySelectorAll('div')).filter((el) => (el.innerText || '').trim().startsWith(label));
      hits.sort((a, b) => a.innerText.length - b.innerText.length);
      return hits[0] || null;
    }, label);
    const el = h.asElement(); if (!el) throw new Error('nothing to tap: ' + label);
    await el.evaluate((n) => n.scrollIntoView({ block: 'center' })); await el.click();
  };
  await page.goto(APP_URL, { waitUntil: 'networkidle2', timeout: 60000 });
  await page.waitForSelector('input[placeholder], textarea[placeholder]', { timeout: 45000 }).catch(async (e) => { await page.screenshot({ path: `${OUT}/intake_failed.png` }); console.log(await page.evaluate(() => document.body.innerText.slice(0, 300))); throw e; });
  let v = await next(async () => { await page.type('input[placeholder], textarea[placeholder]', TOPIC); await page.keyboard.press('Enter'); });
  for (let turn = 0; turn < 12 && v && v.question; turn++) {
    const q = v.question;
    console.log(`\n[${q.id}] (${q.source || 'default'}) ${q.prompt}`);
    (q.options || []).forEach((o) => console.log('   -', o.label, '|', o.hint || ''));
    if (q.id === 'framework' || q.id === 'context') { await sleep(400); await page.screenshot({ path: `${OUT}/intake_${q.id}_${WIDTH}.png` }); }
    if (q.id === 'context') break;
    const first = (q.options || [])[0];
    if (first) v = await next(() => tap(first.label));
    else v = await next(async () => { await page.type('input[placeholder], textarea[placeholder]', 'Class 8 students'); await page.keyboard.press('Enter'); });
  }
  await browser.close();
})().catch((e) => { console.error('driver crashed:', e); process.exit(2); });
