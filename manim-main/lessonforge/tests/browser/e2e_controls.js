// The "All controls" panel on the read-back, in a real browser: every group the server lists is there, a toggle,
// a number and a model list can be changed, the count of changes follows, and what is POSTed to /generate carries
// exactly those settings. The POST is intercepted and never reaches the server: nothing is started, nothing is spent.
// Usage: APP_URL=https://…/app/?token=… [OUT=dir] node e2e_controls.js [width height]
const puppeteer = require('puppeteer-core');
const fs = require('fs');

const APP_URL = process.env.APP_URL;
const OUT = process.env.OUT || 'out_controls';
const WIDTH = parseInt(process.argv[2] || '390', 10), HEIGHT = parseInt(process.argv[3] || '844', 10);
const SCRIPT = `# Half aur one fourth

Ek roti lijiye. Agar hum ise do equal parts mein kaatein, toh har part ko one half kehte hain.

## Chhote tukde
Ab usi roti ko 4 equal parts mein kaatiye. Har part ab one fourth hai.
Toh batao, one half bada hai ya one fourth?

## Jawab
One half bada hai. Yaad rakhiye: neeche ka number jitna bada, tukda utna chhota.
`;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const problems = [], log = (...a) => console.log(...a);
const fail = (msg) => { problems.push(msg); log('  ✗', msg); };
fs.mkdirSync(OUT, { recursive: true });

(async () => {
  const browser = await puppeteer.launch({ executablePath: process.env.CHROME || '/usr/bin/google-chrome', headless: 'new', args: ['--no-sandbox'] });
  const page = await browser.newPage();
  await page.setViewport({ width: WIDTH, height: HEIGHT });
  let catalogue = null, sent = null;
  page.on('pageerror', (e) => fail('page error: ' + String(e).slice(0, 300)));
  page.on('console', (m) => { if (m.type() === 'error' && !/favicon|net::ERR_FAILED/.test(m.text())) fail('console error: ' + m.text().slice(0, 300)); });
  await page.setRequestInterception(true);
  page.on('request', (req) => {
    if (/\/api\/harness\/generate$/.test(req.url()) && req.method() === 'POST') {
      sent = JSON.parse(req.postData() || '{}');
      log('   intercepted POST /generate (not sent): settings = ' + JSON.stringify(sent.settings));
      return req.abort();
    }
    return req.continue();
  });
  page.on('response', async (res) => {
    if (res.status() >= 400 && !/favicon/.test(res.url())) fail(`HTTP ${res.status()} ${res.url().replace(/token=[^&]+/, 'token=…').slice(0, 140)}`);
    try { if (/\/api\/harness\/controls/.test(res.url())) catalogue = await res.json(); } catch (e) { /* not JSON */ }
  });
  const shot = (name) => page.screenshot({ path: `${OUT}/controls_${name}_${WIDTH}.png`, fullPage: false });
  const text = () => page.evaluate(() => document.body.innerText);
  const waitText = async (needle, ms = 30000) => {
    const end = Date.now() + ms;
    while (Date.now() < end) { if ((await text()).includes(needle)) return true; await sleep(250); }
    return false;
  };
  // The smallest element whose text is exactly `label`, or (startsWith) whose text begins with it.
  const clickText = async (label, startsWith = false) => {
    const handle = await page.evaluateHandle((label, startsWith) => {
      const all = Array.from(document.querySelectorAll('div, span, button, input'));
      const hits = all.filter((el) => { const t = (el.innerText || '').trim(); return startsWith ? t.startsWith(label) : t === label; });
      hits.sort((a, b) => a.querySelectorAll('*').length - b.querySelectorAll('*').length);
      return hits[0] || null;
    }, label, startsWith);
    const el = handle.asElement();
    if (!el) return false;
    await el.evaluate((n) => n.scrollIntoView({ block: 'center' }));
    await el.click();
    await sleep(150);
    return true;
  };
  // The Nth sibling chip ("On"/"Off", "−"/"+") under the row whose label is `label`.
  const clickInRow = async (label, chip) => {
    const handle = await page.evaluateHandle((label, chip) => {
      const all = Array.from(document.querySelectorAll('div'));
      const labelEl = all.filter((el) => (el.innerText || '').trim() === label).sort((a, b) => a.querySelectorAll('*').length - b.querySelectorAll('*').length)[0];
      if (!labelEl) return null;
      let row = labelEl;
      for (let i = 0; i < 4 && row; i++) {
        const found = Array.from(row.querySelectorAll('div')).filter((el) => (el.innerText || '').trim().split('\n')[0] === chip && el !== labelEl);
        found.sort((a, b) => a.querySelectorAll('*').length - b.querySelectorAll('*').length);
        if (found[0]) return found[0];
        row = row.parentElement;
      }
      return null;
    }, label, chip);
    const el = handle.asElement();
    if (!el) return false;
    await el.evaluate((n) => n.scrollIntoView({ block: 'center' }));
    await el.click();
    await sleep(150);
    return true;
  };

  log(`→ ${APP_URL.replace(/token=[^&]+/, 'token=…')}  (${WIDTH}×${HEIGHT})`);
  await page.goto(APP_URL, { waitUntil: 'networkidle2', timeout: 60000 });
  if (!(await waitText('Make a lesson video', 20000))) fail('start screen did not render');
  if (!(await clickText('Use my script'))) fail('no "Use my script" switch');
  const box = await page.$('textarea');
  if (!box) { fail('no textarea for the script'); throw new Error('cannot continue'); }
  await box.click();
  await box.type(SCRIPT, { delay: 0 });
  if (!(await clickText('Check my script'))) fail('no "Check my script" button');
  if (!(await waitText('Here is what I will make', 20000))) fail('the read-back did not appear');
  if (!(await waitText('All controls', 10000))) { fail('no "All controls" panel on the read-back'); throw new Error('cannot continue'); }
  if (!catalogue) fail('the app did not fetch GET /controls');
  const before = await text();
  if (!/All controls\s*\n?\s*server defaults/.test(before.replace(/\s+/g, ' ').replace('All controls server defaults', 'All controls\nserver defaults'))) {
    if (!before.includes('server defaults')) fail('the folded panel does not say "server defaults"');
  }
  await shot('01_folded');
  await clickText('All controls');
  await sleep(300);
  const opened = await text();
  for (const group of catalogue ? catalogue.groups : []) if (!opened.includes(group)) fail(`group not listed: ${group}`);
  if (opened.includes("The hand's marks")) fail('a group is open before being tapped');
  await shot('02_groups');

  // Pictures: a toggle off.
  await clickText('Pictures');
  if (!(await waitText("The hand's marks", 3000))) fail('the Pictures group did not open');
  if (!(await clickInRow("The hand's marks", 'Off'))) fail('could not tap Off on "The hand\'s marks"');
  if (!(await waitText('1 changed', 3000))) fail('the count did not become "1 changed"');
  await shot('03_toggle');
  // Writing: a number down.
  await clickText('Pictures');       // fold it
  await clickText('Writing');
  if (!(await waitText('Review rounds', 3000))) fail('the Writing group did not open');
  if (!(await clickInRow('Review rounds', '−'))) fail('could not tap − on "Review rounds"');
  if (!(await waitText('2 changed', 3000))) fail('the count did not become "2 changed"');
  // Models: the writer's list.
  await clickText('Writing');
  await clickText('Models');
  if (!(await waitText('Writer', 3000))) fail('the Models group did not open');
  const inputs = await page.$$('input');
  let writerBox = null;
  for (const input of inputs) {
    const placeholder = await input.evaluate((n) => n.placeholder || '');
    if (/claude-haiku/.test(placeholder)) { writerBox = input; break; }
  }
  if (!writerBox) fail('no text box for the writer models');
  else {
    await writerBox.click({ clickCount: 3 });
    await writerBox.type('anthropic/claude-haiku-5.5', { delay: 0 });
    if (!(await waitText('3 changed', 3000))) fail('the count did not become "3 changed"');
  }
  await shot('04_models');
  // Look: a choice that only the render sees.
  await clickText('Models');
  await clickText('Look of the video');
  if (!(await waitText('A question card shows', 3000))) fail('the Look group did not open');
  if (!(await clickText('The options too'))) fail('could not pick "The options too"');
  if (!(await waitText('4 changed', 3000))) fail('the count did not become "4 changed"');
  // A reset of one row.
  if (!(await clickInRow('A question card shows', 'reset'))) fail('no per-row reset');
  if (!(await waitText('3 changed', 3000))) fail('the row reset did not take the count back to 3');

  // Generate: the POST is intercepted and aborted; what it carried is the check.
  if (!(await clickText('Generate video'))) fail('no "Generate video" button');
  await sleep(1500);
  if (!sent) fail('nothing was posted to /generate');
  else {
    const expected = { HARNESS_ANNOTATE: '0', HARNESS_CRITIC_ROUNDS: '1', HARNESS_WRITER_MODELS: 'anthropic/claude-haiku-5.5' };
    if (JSON.stringify(sent.settings) !== JSON.stringify(expected)) fail(`settings posted ${JSON.stringify(sent.settings)}, expected ${JSON.stringify(expected)}`);
    if (!sent.brief || sent.brief.mode !== 'script') fail('the brief was not the script');
  }
  await shot('05_after');
  log(problems.length ? `\nFAILED with ${problems.length} problem(s):\n - ` + problems.join('\n - ') : '\nCONTROLS OK (nothing generated, nothing spent)');
  await browser.close();
  process.exit(problems.length ? 1 : 0);
})().catch((e) => { log('driver error: ' + e.message); process.exit(2); });
