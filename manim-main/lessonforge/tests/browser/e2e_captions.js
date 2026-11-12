// Captions are a line of the PAGE under the video, never drawn on the picture while the video is in the page.
// On an EXISTING finished lesson, in a real browser; nothing is generated and nothing is spent.
//   in the page the caption track is loaded but hidden, and the line under the video says the words being spoken
//   a long sentence is shown in pieces that fit the line, one after the other, with no word lost
//   the line stands directly under the video, as wide as it, never changes its height (the page under it does not
//   move), and the page does not scroll sideways
//   "CC" turns the line off and on, and the choice is still there after a reload
//   in full screen the browser draws the captions (the page's line cannot be seen there) and gives them back after
// Usage: APP_URL='https://…/app/?token=…' JOB=<job id> [OUT=dir] node e2e_captions.js [width height]
const puppeteer = require('puppeteer-core');
const fs = require('fs');

const APP_URL = process.env.APP_URL, JOB = process.env.JOB, OUT = process.env.OUT || 'out';
const WIDTH = parseInt(process.argv[2] || '412', 10), HEIGHT = parseInt(process.argv[3] || '880', 10);
const MOST = 84;                       // src/captions.ts CAPTION_CHARS
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const problems = [], log = (...a) => console.log(...a);
const fail = (msg) => { problems.push(msg); log('  ✗', msg); };
const ok = (msg) => log('  ✓', msg);
fs.mkdirSync(OUT, { recursive: true });

function cuesOf(vtt) {
  const seconds = (stamp) => stamp.trim().split(':').map(parseFloat).reduce((sum, part) => sum * 60 + part, 0);
  const cues = [];
  for (const block of vtt.replace(/\r/g, '').split(/\n\n+/)) {
    const lines = block.split('\n'), at = lines.findIndex((l) => l.includes('-->'));
    if (at < 0) continue;
    const [start, end] = lines[at].split('-->');
    cues.push({ start: seconds(start), end: seconds(end.trim().split(' ')[0]), text: lines.slice(at + 1).join(' ').replace(/<[^>]*>/g, '').replace(/\s+/g, ' ').trim() });
  }
  return cues;
}

(async () => {
  const browser = await puppeteer.launch({ executablePath: process.env.CHROME || '/usr/bin/google-chrome', headless: 'new',
    args: ['--no-sandbox', '--autoplay-policy=no-user-gesture-required'] });
  const page = await browser.newPage();
  await page.setViewport({ width: WIDTH, height: HEIGHT });
  let vtt = null;
  page.on('pageerror', (e) => fail('page error: ' + String(e).slice(0, 300)));
  page.on('console', (m) => { if (m.type() === 'error' && !/favicon/.test(m.text())) fail('console error: ' + m.text().slice(0, 300)); });
  page.on('response', async (res) => {
    const url = res.url();
    if (res.status() >= 400 && !/favicon/.test(url)) fail(`HTTP ${res.status()} ${url.replace(/token=[^&]+/, 'token=…').slice(0, 140)}`);
    try { if (/captions[^/]*\.vtt/.test(url) && res.status() === 200) vtt = await res.text(); } catch (e) { /* gone */ }
  });
  const shot = (name) => page.screenshot({ path: `${OUT}/${name}.png` });
  // What the page shows and what the browser would draw, read from the page itself.
  const state = () => page.evaluate(() => {
    const video = document.querySelector('video');
    if (!video) return null;
    const track = Array.from(video.textTracks).find((t) => t.kind === 'captions' || t.kind === 'subtitles') || null;
    const box = video.getBoundingClientRect();
    const toggle = Array.from(document.querySelectorAll('[aria-label]')).find((el) => /^Turn captions (on|off)$/.test(el.getAttribute('aria-label')));
    const line = toggle ? toggle.parentElement : null;
    const lineBox = line ? line.getBoundingClientRect() : null;
    const words = line && toggle ? (line.innerText || '').replace((toggle.innerText || ''), '').replace(/\s+/g, ' ').trim() : '';
    return {
      time: video.currentTime, paused: video.paused, mode: track ? track.mode : null, cues: track && track.cues ? track.cues.length : 0,
      active: track && track.activeCues && track.activeCues.length ? track.activeCues[track.activeCues.length - 1].text : '',
      video: { top: box.top, bottom: box.bottom, left: box.left, width: box.width },
      line: lineBox ? { top: lineBox.top, left: lineBox.left, width: lineBox.width, height: lineBox.height } : null,
      toggle: toggle ? toggle.getAttribute('aria-label') : null, words,
      fullscreen: document.fullscreenElement === video,
      sideways: document.documentElement.scrollWidth - window.innerWidth,
    };
  });
  const video = (fn, arg) => page.evaluate(new Function('arg', `const v = document.querySelector('video'); if (!v) return null; ${fn}`), arg);
  const pressToggle = async () => {
    const handle = await page.evaluateHandle(() => Array.from(document.querySelectorAll('[aria-label]')).find((el) => /^Turn captions (on|off)$/.test(el.getAttribute('aria-label'))) || null);
    const el = handle.asElement();
    if (!el) return false;
    await el.evaluate((n) => n.scrollIntoView({ block: 'center' }));
    await el.click();
    await sleep(500);
    return true;
  };
  const open = async () => {
    await page.goto(APP_URL + '#job=' + JOB, { waitUntil: 'networkidle2', timeout: 60000 });
    const end = Date.now() + 20000;
    while (Date.now() < end && !(await page.$('video'))) await sleep(300);
    await sleep(1500);
  };

  log(`→ ${(APP_URL + '#job=' + JOB).replace(/token=[^&#]+/, 'token=…')}  (${WIDTH}×${HEIGHT})`);
  await open();
  if (!(await page.$('video'))) { fail('the lesson did not open from its link'); await shot('c0_failed'); await browser.close(); process.exit(1); }
  await video('v.muted = true; v.play(); return true;');
  await sleep(2500);
  await video('v.pause(); return true;');
  let s = await state();
  const cues = cuesOf(vtt || '');
  log(`   caption file: ${cues.length} cues; track in the page: ${s.cues} cues, mode ${s.mode}`);
  if (!cues.length) fail('the caption file was not loaded');

  // 1. in the page nothing is drawn on the picture
  if (s.mode === 'hidden') ok('the caption track is loaded and hidden: the browser draws nothing on the picture');
  else fail(`the caption track is "${s.mode}" in the page (wanted "hidden")`);
  if (!s.line) fail('there is no caption line under the video');

  // 2. the line says what is being spoken
  const short = cues.find((c) => c.text.length <= MOST && c.end - c.start > 1.5);
  if (short && s.line) {
    await video('v.currentTime = arg; return true;', (short.start + short.end) / 2);
    await sleep(900);
    s = await state();
    if (s.words === short.text) ok(`at ${((short.start + short.end) / 2).toFixed(1)} s the line reads the sentence being spoken: “${s.words.slice(0, 60)}”`);
    else fail(`at ${((short.start + short.end) / 2).toFixed(1)} s the line reads “${s.words}” and the caption file says “${short.text}”`);
    await shot('c1_line');
  }

  // 3. a long sentence comes in pieces, in order, with every word
  const long = cues.filter((c) => c.text.length > MOST).sort((a, b) => b.text.length - a.text.length)[0];
  if (long && s.line) {
    const seen = [], heights = new Set();
    for (let k = 0; k < 24; k++) {
      await video('v.currentTime = arg; return true;', long.start + (long.end - long.start) * (k + 0.5) / 24);
      await sleep(350);
      const now = await state();
      heights.add(Math.round(now.line.height));
      if (now.words && seen[seen.length - 1] !== now.words) seen.push(now.words);
    }
    const longest = Math.max(...seen.map((piece) => piece.length));
    // On a wide page the whole sentence may stand on one line: then it is one piece, and that is right.
    if (seen.join(' ') === long.text && longest <= MOST) ok(`a sentence of ${long.text.length} characters is shown in ${seen.length} piece(s), the longest ${longest}, no word lost`);
    else fail(`a sentence of ${long.text.length} characters was shown as ${JSON.stringify(seen)}`);
    if (heights.size === 1) ok(`the line stays ${[...heights][0]} px high through all of it`);
    else fail(`the line's height changed while the sentence was shown: ${[...heights].join(', ')} px`);
    await shot('c2_long');
  } else log('   (no sentence longer than two lines in this lesson)');

  // 4. where the line stands
  s = await state();
  if (s.line) {
    const gap = s.line.top - s.video.bottom;
    if (gap >= 0 && gap <= 16) ok(`the line begins ${gap.toFixed(0)} px under the video`); else fail(`the line begins ${gap.toFixed(0)} px from the video's foot`);
    if (Math.abs(s.line.width - s.video.width) <= 2 && Math.abs(s.line.left - s.video.left) <= 2) ok(`it is as wide as the video (${s.video.width.toFixed(0)} px)`);
    else fail(`the line is ${s.line.width.toFixed(0)} px wide at ${s.line.left.toFixed(0)}, the video ${s.video.width.toFixed(0)} at ${s.video.left.toFixed(0)}`);
    const between = cues.find((c, i) => cues[i + 1] && cues[i + 1].start - c.end > 0.8);
    if (between) {                      // nothing is being said: the line is empty and as tall as with words
      const tall = s.line.height;
      await video('v.currentTime = arg; return true;', between.end + 0.4);
      await sleep(900);
      const quiet = await state();
      if (!quiet.words && Math.abs(quiet.line.height - tall) <= 1) ok('between sentences the line is empty and keeps its height: the page under it does not move');
      else if (quiet.words) log(`   (a sentence was still up at ${(between.end + 0.4).toFixed(1)} s: “${quiet.words.slice(0, 40)}”)`);
      else fail(`the line is ${quiet.line.height.toFixed(0)} px high when empty and ${tall.toFixed(0)} px with words`);
    }
  }
  if (s.sideways > 1) fail(`the page scrolls sideways by ${s.sideways} px`); else ok('the page does not scroll sideways');

  // 5. off, remembered, and on again
  if (await pressToggle()) {
    s = await state();
    if (s.mode === 'disabled' && !s.words && s.toggle === 'Turn captions on') ok('"CC" turns the captions off'); else fail(`after "CC": mode ${s.mode}, line “${s.words}”, switch “${s.toggle}”`);
    await shot('c3_off');
    await open();
    await video('v.muted = true; v.play(); return true;');
    await sleep(2000);
    await video('v.pause(); return true;');
    s = await state();
    if (s.mode === 'disabled' && s.toggle === 'Turn captions on') ok('the choice is kept after a reload'); else fail(`after a reload: mode ${s.mode}, switch “${s.toggle}”`);
    await pressToggle();
    s = await state();
    if (s.mode === 'hidden' && s.toggle === 'Turn captions off') ok('and they come back on'); else fail(`turned on again: mode ${s.mode}, switch “${s.toggle}”`);
  } else fail('no captions switch was found');

  // 6. full screen: the browser draws them there, and the page takes them back
  const went = await page.evaluate(async () => { try { await document.querySelector('video').requestFullscreen(); return true; } catch (e) { return String(e); } });
  await sleep(900);
  s = await state();
  if (went !== true || !s.fullscreen) log(`   (this browser did not go full screen: ${went}; not checked)`);
  else {
    if (s.mode === 'showing') ok('in full screen the browser draws the captions'); else fail(`in full screen the track is "${s.mode}"`);
    await page.evaluate(async () => { try { await document.exitFullscreen(); } catch (e) { /* already out */ } });
    await sleep(900);
    s = await state();
    if (s.mode === 'hidden') ok('back in the page they are the page\'s again'); else fail(`after full screen the track is "${s.mode}"`);
  }

  await browser.close();
  log(problems.length ? `\n${problems.length} PROBLEM(S)` : '\nALL OK');
  process.exit(problems.length ? 1 : 0);
})().catch((e) => { console.error('FAILED', e); process.exit(1); });
