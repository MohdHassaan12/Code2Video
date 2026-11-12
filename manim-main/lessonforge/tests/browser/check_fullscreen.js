// Does a question still reach the viewer when the video is fullscreen? (Headless Chrome, native fullscreen.)
//   APP_URL='https://…/app/?token=…' JOB=<job id> node check_fullscreen.js
const puppeteer = require('puppeteer-core');
const APP_URL = process.env.APP_URL, JOB = process.env.JOB;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
(async () => {
  const browser = await puppeteer.launch({ executablePath: '/usr/bin/google-chrome', headless: 'new', args: ['--no-sandbox', '--autoplay-policy=no-user-gesture-required'] });
  const page = await browser.newPage();
  await page.setViewport({ width: 1180, height: 860 });
  let interactions = null;
  page.on('response', async (res) => { try { if (/interactions\.json/.test(res.url())) interactions = await res.json(); } catch (e) { /* ignore */ } });
  await page.goto(APP_URL + '#job=' + JOB, { waitUntil: 'networkidle2', timeout: 60000 });
  await page.waitForSelector('video', { timeout: 30000 });
  await sleep(1500);
  const q = interactions && interactions.interactions[0];
  if (!q) { console.log('no questions on this lesson'); process.exit(1); }
  await page.click('video');                       // a user gesture, so fullscreen is allowed
  const entered = await page.evaluate(() => document.querySelector('video').requestFullscreen().then(() => !!document.fullscreenElement).catch((e) => String(e)));
  await page.evaluate((t) => { const v = document.querySelector('video'); v.muted = true; v.currentTime = t; return v.play().catch(() => {}); }, Math.max(0, q.t - 2.5));
  await sleep(6000);
  const state = await page.evaluate(() => ({ fullscreen: !!document.fullscreenElement, paused: document.querySelector('video').paused,
    asking: /your turn/i.test(document.body.innerText), t: document.querySelector('video').currentTime }));
  console.log('entered fullscreen:', entered, '| at the question:', JSON.stringify(state), '| question t =', q.t);
  console.log(state.asking && !state.fullscreen ? 'OK: the player left fullscreen and is asking' : 'PROBLEM: the question is not visible to a fullscreen viewer');
  await browser.close();
})().catch((e) => { console.error('driver crashed:', e); process.exit(2); });
