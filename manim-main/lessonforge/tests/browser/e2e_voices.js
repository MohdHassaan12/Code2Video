// The voice choices (2026-10-15) in a real browser, on a server with no keys (nothing is spent):
//  1. the script flow's confirm screen shows the voices grouped, filtered to the script's language, each with its cost;
//  2. a lesson narrated with the learner's own device (voice "browser:<lang>") has its captions read aloud by the
//     browser's speechSynthesis as the video plays (stubbed here, so the test hears what was asked to be spoken).
// Usage: APP_URL=http://127.0.0.1:5055/app/ JOB=<a lesson whose voice is browser:en-IN> OUT=/dir node e2e_voices.js
const puppeteer = require('puppeteer-core');

const APP_URL = process.env.APP_URL, JOB = process.env.JOB, OUT = process.env.OUT || '.';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const problems = [], log = (...a) => console.log(...a);
const fail = (msg) => { problems.push(msg); log('  ✗', msg); };
const SCRIPT = 'Light bounces off a mirror. The angle in equals the angle out. We measure both from the normal, the line at a right angle to the mirror. If a ray comes in at thirty degrees, it leaves at thirty degrees.';

(async () => {
  const browser = await puppeteer.launch({ executablePath: '/usr/bin/google-chrome', headless: 'new',
    args: ['--no-sandbox', '--autoplay-policy=no-user-gesture-required'] });
  const page = await browser.newPage();
  await page.setViewport({ width: 1180, height: 900 });
  page.on('pageerror', (e) => fail('page error: ' + String(e).slice(0, 300)));
  page.on('console', (m) => { if (m.type() === 'error' && !/favicon/.test(m.text())) fail('console error: ' + m.text().slice(0, 300)); });
  // What the page asks the device to say is recorded instead of spoken.
  await page.evaluateOnNewDocument(() => {
    window.__spoken = [];
    const synth = window.speechSynthesis;
    if (synth) {
      synth.speak = (u) => window.__spoken.push({ text: u.text, lang: u.lang, at: document.querySelector('video')?.currentTime ?? -1 });
      synth.cancel = () => window.__spoken.push({ cancel: true });
    }
  });
  const shot = (name) => page.screenshot({ path: `${OUT}/${name}.png`, fullPage: true });
  const text = () => page.evaluate(() => document.body.innerText);
  const waitText = async (needle, ms = 20000) => { const end = Date.now() + ms; while (Date.now() < end) { if ((await text()).includes(needle)) return true; await sleep(200); } return false; };
  const clickText = async (label) => {
    const handle = await page.evaluateHandle((label) => {
      const all = Array.from(document.querySelectorAll('div, span, button'));
      const hits = all.filter((el) => (el.innerText || '').trim() === label);
      hits.sort((a, b) => b.querySelectorAll('*').length - a.querySelectorAll('*').length);
      return hits[hits.length - 1] || null;
    }, label);
    const el = handle.asElement();
    if (!el) return false;
    await el.click();
    return true;
  };

  // 1. The voice picker, on the script flow's confirm screen.
  await page.goto(APP_URL, { waitUntil: 'networkidle2', timeout: 60000 });
  if (!(await waitText('Make a lesson video'))) fail('start screen did not render');
  if (!(await clickText('Use my script'))) fail('no "Use my script" switch');
  const box = await page.$('textarea');
  if (!box) { fail('no script box'); } else { await box.click(); await box.type(SCRIPT, { delay: 0 }); }
  const audience = await page.$('input[placeholder="e.g. Class 8 students"]');
  if (audience) await audience.type('Class 7 students', { delay: 2 });
  if (!(await clickText('Check my script'))) fail('no "Check my script" button');
  if (!(await waitText('Here is what I will make'))) fail('the read-back did not appear');
  for (const needle of ['Voice', 'MICROSOFT VOICES (ONLINE)', 'Neerja', 'Prabhat', "LEARNER'S DEVICE"]) {
    if (!(await waitText(needle, 8000))) fail(`voice picker: "${needle}" not shown`);
  }
  if ((await text()).includes('Swara')) fail('a Hindi voice is offered for an English script');
  await clickText('Neerja');
  if (!(await waitText("Free: Microsoft's online voices", 5000))) fail('no cost line for Neerja');
  if (!(await waitText('about 0.15 cents a minute', 3000))) fail('no word-timing cost under a narrated voice');
  await shot('01_voices_neerja');
  await clickText("Learner's device");
  if (!(await waitText("the learner's device reads the captions aloud", 5000))) fail("no cost line for the learner's device");
  if ((await text()).includes('about 0.15 cents a minute')) fail("word timing is priced for the device voice, which is not timed");
  await shot('02_voices_device');
  log('picker checked');

  // 2. A lesson narrated by the device: its captions are read aloud as it plays.
  await page.goto('about:blank');                       // a change of #hash alone would not reload the app
  await page.goto(`${APP_URL}#job=${JOB}`, { waitUntil: 'networkidle2', timeout: 60000 });
  const video = await page.waitForSelector('video', { timeout: 30000 }).catch(() => null);
  if (!video) { fail('the lesson did not open'); }
  else {
    await page.evaluate(() => { const v = document.querySelector('video'); v.muted = true; return v.play(); }).catch(() => {});
    await sleep(9000);
    const spoken = (await page.evaluate(() => window.__spoken)).filter((s) => s.text);
    log(`spoken while playing: ${spoken.length}`, spoken.slice(0, 3));
    if (!spoken.length) fail('nothing was read aloud while the video played');
    if (spoken.some((s) => s.lang !== 'en-IN')) fail('read in the wrong language');
    // A pause stops the reading; playing again goes on.
    await page.evaluate(() => document.querySelector('video').pause());
    await sleep(500);
    const afterPause = await page.evaluate(() => window.__spoken.length);
    await sleep(2500);
    if ((await page.evaluate(() => window.__spoken.length)) !== afterPause) fail('it went on reading while paused');
    await shot('03_device_voice');
  }
  await browser.close();
  log(problems.length ? `FAILED: ${problems.length} problem(s)` : 'ALL PASSED');
  process.exit(problems.length ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(2); });
