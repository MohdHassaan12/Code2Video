// One tall screenshot of the dashboard as its owner sees it (test browsers left out).
//   APP_URL='https://…/app/?token=…' [OUT=dir] node shot_dashboard.js [width height]
const puppeteer = require('puppeteer-core');
const APP_URL = process.env.APP_URL, OUT = process.env.OUT || 'out';
const WIDTH = parseInt(process.argv[2] || '1180', 10), HEIGHT = parseInt(process.argv[3] || '2600', 10);
require('fs').mkdirSync(OUT, { recursive: true });
(async () => {
  const browser = await puppeteer.launch({ executablePath: process.env.CHROME || '/usr/bin/google-chrome', headless: 'new', args: ['--no-sandbox'] });
  const page = await browser.newPage();
  await page.setViewport({ width: WIDTH, height: HEIGHT });
  await page.goto(APP_URL + '#dashboard', { waitUntil: 'networkidle2', timeout: 60000 });
  await page.waitForFunction(() => /lessons made/i.test(document.body.innerText), { timeout: 20000 });
  await new Promise((r) => setTimeout(r, 800));
  await page.screenshot({ path: `${OUT}/dashboard_${WIDTH}.png` });
  await browser.close();
})().catch((e) => { console.error(e); process.exit(2); });
