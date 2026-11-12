// The question ladder in a real browser, on a side server (no keys) with a COPY of a finished lesson whose
// interactions.json was written by today's service.write_interactions (on_wrong, confidence):
// "How sure?" -> wrong -> nudge, no answer yet -> wrong again -> the answer + "Watch that part again" -> the video
// goes back and plays -> the question comes up again there.
// Playwright's open-source Chromium has no H.264: re-encode the copy's video to VP9 (same file name) first, e.g.
//   ffmpeg -i in.mp4 -vf scale=640:-2 -c:v libvpx-vp9 -deadline realtime -cpu-used 8 -c:a libopus -f webm out && mv out in.mp4
// Usage: node e2e_ladder.js http://localhost:5055/app/ <job id> <out dir>
const { chromium } = require('/opt/node-tools/node_modules/playwright');
const [APP, JOB, OUT] = process.argv.slice(2);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const problems = []; const fail = (m) => { problems.push(m); console.log('  ✗', m); };
(async () => {
  const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome', args: ['--autoplay-policy=no-user-gesture-required'] });
  const page = await browser.newPage({ viewport: { width: 1180, height: 900 } });
  page.on('pageerror', (e) => fail('page error: ' + String(e).slice(0, 200)));
  let inter = null;
  page.on('response', async (r) => { if (/interactions\.json/.test(r.url())) { try { inter = await r.json(); } catch {} } });
  const text = () => page.evaluate(() => document.body.innerText);
  const waitText = async (s, ms = 12000) => { const e = Date.now() + ms; while (Date.now() < e) { if ((await text()).includes(s)) return true; await sleep(200); } return false; };
  const tap = async (label) => { const el = page.getByText(label, { exact: true }).last(); if (!(await el.count())) return false; await el.click(); return true; };
  await page.goto(APP + '#job=' + JOB, { waitUntil: 'networkidle' });
  await page.waitForSelector('video', { timeout: 20000 });
  await sleep(1500);
  const q = inter.interactions.find((x) => x.on_wrong && x.options.length >= 3);
  console.log('question', q.id, q.kind, 't', q.t, 'back to', q.on_wrong.seek_to);
  await page.evaluate((t) => { const v = document.querySelector('video'); v.muted = true; v.currentTime = t; v.play(); }, q.t - 2.5);
  if (!(await waitText('How sure are you?'))) fail('no "How sure are you?" row');
  await page.screenshot({ path: OUT + '/l1_asked.png' });
  await tap('Sure');
  const wrong = q.options.filter((o) => !o.correct);
  await tap(wrong[0].text);
  if (!(await waitText('Not yet. Try once more.', 3000))) fail('no nudge after the first wrong answer');
  if ((await text()).includes('The answer is')) fail('the answer was shown after only one try');
  await page.screenshot({ path: OUT + '/l2_nudge.png' });
  await tap(wrong[1].text);
  if (!(await waitText('The answer is', 3000))) fail('the answer was not shown after the second wrong try');
  if (!(await waitText('Watch that part again', 2000))) fail('no "Watch that part again"');
  await page.screenshot({ path: OUT + '/l3_answer.png' });
  await tap('↺ Watch that part again');
  await sleep(1500);
  const at = await page.evaluate(() => { const v = document.querySelector('video'); return { t: v.currentTime, paused: v.paused }; });
  console.log('after rewatch', at);
  if (Math.abs(at.t - q.on_wrong.seek_to) > 3 || at.paused) fail('did not go back and play from ' + q.on_wrong.seek_to);
  if ((await text()).toUpperCase().includes('YOUR TURN')) fail('the card stayed up after "Watch that part again"');
  // second sitting at the same question: right on the first tap now, the first answer still counts as wrong
  await page.evaluate((t) => { const v = document.querySelector('video'); v.currentTime = t; v.play(); }, q.t - 2.5);
  if (!(await waitText('YOUR TURN'))) fail('the question did not come back after watching again');
  await tap(q.options.find((o) => o.correct).text);
  if (!(await waitText('Correct', 3000))) fail('no verdict on the second sitting');
  const score = (await text()).match(/Questions: [^\n]*/);
  console.log('score line:', score && score[0]);
  await page.screenshot({ path: OUT + '/l4_again.png' });
  await browser.close();
  console.log(problems.length ? `FAILED (${problems.length})` : 'OK');
  process.exit(problems.length ? 1 : 0);
})();
