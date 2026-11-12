// A video made FROM A PASTED SCRIPT, in a real browser, through the public URL:
// "Use my script" → paste → "Check my script" (the read-back) → generate → the video plays →
// a reload reopens it → "Edit the script and make it again" brings the words back → history tags it.
// Usage: APP_URL=https://…/app/?token=… [OUT=dir] [SCRIPT=file.txt] [GENERATE=0] node e2e_script.js [width height]
//   GENERATE=0 stops at the read-back: nothing is spent.
const puppeteer = require('puppeteer-core');
const fs = require('fs');

const APP_URL = process.env.APP_URL;
const OUT = process.env.OUT || 'out';
const GENERATE = process.env.GENERATE !== '0';
const WIDTH = parseInt(process.argv[2] || '390', 10), HEIGHT = parseInt(process.argv[3] || '844', 10);
const SCRIPT = process.env.SCRIPT ? fs.readFileSync(process.env.SCRIPT, 'utf8') : `# Half aur one fourth

Ek roti lijiye. [ek gol roti dikhaiye, jo beech se do equal parts mein kat-ti hai]
Agar hum ise do equal parts mein kaatein, toh har part ko one half kehte hain.

## Chhote tukde
Ab usi roti ko 4 equal parts mein kaatiye. Har part ab one fourth hai.
Dhyan se dekhiye: parts zyada hue, toh har part chhota ho gaya.
Toh batao, one half bada hai ya one fourth?

## Jawab
One half bada hai. Kyunki jab roti kam parts mein kat-ti hai, toh har part bada milta hai.
Yaad rakhiye: neeche ka number jitna bada, tukda utna chhota.
`;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const problems = [], log = (...a) => console.log(...a);
const fail = (msg) => { problems.push(msg); log('  ✗', msg); };
fs.mkdirSync(OUT, { recursive: true });

(async () => {
  const browser = await puppeteer.launch({ executablePath: process.env.CHROME || '/usr/bin/google-chrome', headless: 'new',
    args: ['--no-sandbox', '--autoplay-policy=no-user-gesture-required'] });
  const page = await browser.newPage();
  await page.setViewport({ width: WIDTH, height: HEIGHT });
  let plan = null, job = null, sent = null, lastStage = '';
  page.on('pageerror', (e) => fail('page error: ' + String(e).slice(0, 300)));
  // A dropped request is the network's doing and the app retries it (the making screen says so): noted, not failed.
  page.on('console', (m) => {
    if (m.type() !== 'error' || /favicon/.test(m.text())) return;
    if (/net::ERR_(NETWORK_CHANGED|INTERNET_DISCONNECTED|CONNECTION_\w+|NAME_NOT_RESOLVED|TIMED_OUT)/.test(m.text())) log('     (network blip: ' + m.text().slice(-40) + ')');
    else fail('console error: ' + m.text().slice(0, 300));
  });
  page.on('request', (req) => { if (/\/api\/harness\/generate$/.test(req.url()) && req.method() === 'POST') sent = JSON.parse(req.postData() || '{}'); });
  page.on('response', async (res) => {
    const url = res.url();
    if (res.status() >= 400 && !/favicon/.test(url)) fail(`HTTP ${res.status()} ${url.replace(/token=[^&]+/, 'token=…').slice(0, 140)}`);
    try {
      if (/\/api\/harness\/script\/preview/.test(url) && res.request().method() === 'POST') plan = await res.json();
      if (/\/api\/harness\/(jobs\/|generate)/.test(url) && res.request().method() !== 'OPTIONS') {
        const j = await res.json();
        // Other answers under /jobs/<id>/ carry the job id too (the try-it answers do): only a record with a status is the job.
        if (j && j.job_id && j.status) { job = j; if (j.stage !== lastStage) { lastStage = j.stage; log(`     job ${j.job_id}: ${j.status} / ${j.stage}`); } }
      }
    } catch (e) { /* not JSON */ }
  });
  const shot = (name) => page.screenshot({ path: `${OUT}/script_${name}_${WIDTH}.png` });
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
      hits.sort((a, b) => a.querySelectorAll('*').length - b.querySelectorAll('*').length);
      return hits[0] || null;
    }, label);
    const el = handle.asElement();
    if (!el) return false;
    await el.evaluate((n) => n.scrollIntoView({ block: 'center' }));
    await el.click();
    return true;
  };
  const scrollDown = () => page.evaluate(() => Array.from(document.querySelectorAll('div'))
    .filter((d) => d.scrollHeight > d.clientHeight + 40 && getComputedStyle(d).overflowY !== 'visible').forEach((d) => { d.scrollTop = d.scrollHeight; }));

  log(`→ ${APP_URL.replace(/token=[^&]+/, 'token=…')}  (${WIDTH}×${HEIGHT})`);
  await page.goto(APP_URL, { waitUntil: 'networkidle2', timeout: 60000 });
  if (!(await waitText('Make a lesson video', 20000))) fail('start screen did not render');
  for (const needle of ['Describe a topic', 'Use my script', 'What should this video teach?']) {
    if (!(await text()).includes(needle)) fail(`start screen lacks "${needle}"`);
  }
  await shot('01_start');
  if (!(await clickText('Use my script'))) fail('no "Use my script" switch');
  if (!(await waitText('Paste the script you want narrated', 5000))) fail('the script form did not open');
  const box = await page.$('textarea');
  if (!box) { fail('no textarea for the script'); throw new Error('cannot continue'); }
  if ((await text()).includes('What should this video teach?')) fail('the topic question is still on screen in script mode');
  // "Check my script" must not fire on an empty box.
  await clickText('Check my script');
  await sleep(600);
  if (plan) fail('an empty script was sent to the server');
  await box.click();
  await box.type(SCRIPT, { delay: 0 });
  const audience = await page.$('input[placeholder="e.g. Class 8 students"]');
  if (!audience) fail('no "who is it for" field'); else await audience.type('Class 6 students', { delay: 2 });
  if (!/\d+ words · about/.test(await text())) fail('no live word count under the script');
  await shot('02_form');
  if (!(await clickText('Check my script'))) fail('no "Check my script" button');
  if (!(await waitText('Here is what I will make', 20000))) fail('the read-back did not appear');
  if (!plan) { fail('no preview came back from the server'); throw new Error('cannot continue'); }
  log(`   read-back: “${plan.title}” · ${plan.words} words · ${plan.minutes} min · ${plan.language} · parts from ${plan.parts_from}`);
  plan.notes.forEach((n) => log('     note: ' + n));
  const confirm = await text();
  for (const row of plan.summary) if (!confirm.includes(row.value.slice(0, 30))) fail(`read-back row not shown: ${row.label} = ${row.value}`);
  for (const chapter of plan.chapters) if (!confirm.includes(chapter.title)) fail(`part not shown: ${chapter.title}`);
  for (const needle of ['Narration language', 'Keep my words exactly', 'Fix mistakes it finds', 'Edit the script', 'Quality']) {
    if (!confirm.includes(needle)) fail(`read-back lacks "${needle}"`);
  }
  if (/\[|dikhaiye/.test(plan.chapters.map((c) => c.opens).join(' ') + plan.opens)) fail('a [direction] is in the words to be spoken');
  await shot('03_readback');
  await scrollDown(); await sleep(300); await shot('04_readback_choices');
  // Going back keeps the words.
  await clickText('Edit the script');
  await sleep(500);
  const kept = await page.$eval('textarea', (t) => t.value).catch(() => '');
  if (kept.trim() !== SCRIPT.trim()) fail('going back to edit lost the script');
  await clickText('Check my script');
  if (!(await waitText('Here is what I will make', 20000))) fail('the read-back did not come back after editing');
  if (!GENERATE) {
    log(problems.length ? `\nFAILED with ${problems.length} problem(s):\n - ` + problems.join('\n - ') : '\nSCRIPT READ-BACK OK (nothing generated)');
    await browser.close();
    process.exit(problems.length ? 1 : 0);
  }

  await clickText('Draft · 480p');
  if (!(await clickText('Generate video'))) fail('no Generate button');
  await sleep(2500);
  if (!sent || !sent.brief || sent.brief.mode !== 'script' || sent.brief.script.trim() !== SCRIPT.trim()) fail('the script was not what was sent: ' + JSON.stringify(sent).slice(0, 200));
  else log(`   sent: mode=${sent.brief.mode} language=${sent.brief.language} script_edit=${sent.brief.script_edit} audience=${sent.brief.audience} quality=${sent.quality}`);
  if (!(await waitText('Planning the picture for your script', 15000))) fail('the making screen does not name the script stage');
  await shot('05_making');
  const deadline = Date.now() + 25 * 60 * 1000;
  while (Date.now() < deadline) {
    if (await page.$('video')) break;
    if ((await text()).includes('Generation failed')) break;
    await sleep(2000);
  }
  if (!job || job.status !== 'done') fail(`job did not finish: ${job && job.status} ${job && job.error}`);
  await sleep(1500);
  const video = await page.$('video');
  if (!video) fail('no <video> element on the result screen');
  else {
    const info = await page.evaluate(async () => {
      const v = document.querySelector('video');
      v.muted = true;
      await new Promise((res) => { if (v.readyState >= 2) return res(); v.addEventListener('loadeddata', res, { once: true }); setTimeout(res, 20000); });
      try { await v.play(); } catch (e) { return { error: String(e), readyState: v.readyState }; }
      await new Promise((r) => setTimeout(r, 4000));
      v.pause();
      return { readyState: v.readyState, duration: v.duration, currentTime: v.currentTime, width: v.videoWidth, height: v.videoHeight, tracks: v.textTracks.length };
    });
    log('   video: ' + JSON.stringify(info));
    if (!(info.readyState >= 2 && info.duration > 5 && info.currentTime > 1)) fail('the video did not play: ' + JSON.stringify(info));
    if (!info.tracks) fail('no caption track on the video');
  }
  const watch = await text();
  for (const needle of ['Made from your script', 'Edit the script and make it again', 'Script check', 'New video']) {
    if (!watch.includes(needle)) fail(`result screen lacks "${needle}"`);
  }
  if (watch.includes('placeholder outline')) fail('a script video is called a placeholder outline');
  await shot('06_watch');
  await scrollDown(); await sleep(400); await shot('07_watch_cards');
  await page.reload({ waitUntil: 'networkidle2' });
  await sleep(2500);
  if (!(await page.$('video'))) fail('after a reload the lesson was not reopened'); else log('   reload: lesson reopened');
  if (!(await clickText('Edit the script and make it again'))) fail('no way back to the script');
  await sleep(800);
  const back = await page.$eval('textarea', (t) => t.value).catch(() => '');
  if (back.trim() !== SCRIPT.trim()) fail('"Edit the script" did not bring the words back'); else log('   edit: the words came back');
  await shot('08_edit_again');
  if (!(await clickText('Start over'))) fail('no "Start over"');
  await sleep(2500);
  const start = await text();
  if (!start.includes('Recent videos') || !start.includes('from a script')) fail('the history does not tag the video as made from a script');
  await shot('09_history');
  log(problems.length ? `\nFAILED with ${problems.length} problem(s):\n - ` + problems.join('\n - ') : '\nE2E SCRIPT OK');
  log('JOB ' + (job ? job.job_id : 'none'));
  await browser.close();
  process.exit(problems.length ? 1 : 0);
})().catch((e) => { console.error('driver crashed:', e); process.exit(2); });
