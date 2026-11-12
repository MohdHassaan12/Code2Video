// One render attempt (see render.mjs, which retries): node scripts/render-once.mjs <render_input.json> <out.mp4>
// The narration is cut from the lesson's audio and laid under the picture with ffmpeg.
import {execFileSync} from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import {renderVideo} from '@revideo/renderer';

process.env.DISABLE_TELEMETRY = 'true';
const [inFile, outFile] = process.argv.slice(2);
const input = JSON.parse(fs.readFileSync(inFile, 'utf8'));
const here = path.dirname(new URL(import.meta.url).pathname);
const outDir = path.resolve(path.dirname(outFile));
const tmpName = `_picture_${process.pid}.mp4`;
const t0 = Date.now();
await renderVideo({
  projectFile: './src/project.ts',
  variables: {input},
  settings: {
    outFile: tmpName, outDir, logProgress: false,
    projectSettings: {exporter: {name: '@revideo/core/ffmpeg', options: {format: 'mp4'}},
      shared: {size: {x: input.width, y: input.height}}, preview: {fps: input.fps}, rendering: {fps: input.fps}},
    puppeteer: {executablePath: process.env.CHROME || path.join(here, 'chrome.sh'), args: ['--no-sandbox']},
  },
});
const picture = path.join(outDir, tmpName);
const first = input.timeline[0], last = input.timeline[input.timeline.length - 1];
const start = first.start, dur = last.start + last.duration - first.start;
if (input.audio && fs.existsSync(input.audio)) {
  execFileSync('ffmpeg', ['-v', 'error', '-y', '-i', picture, '-ss', String(start), '-t', String(dur), '-i', input.audio,
    '-map', '0:v', '-map', '1:a', '-c:v', 'copy', '-c:a', 'aac', '-shortest', outFile]);
  fs.unlinkSync(picture);
} else {
  fs.renameSync(picture, outFile);
}
console.log(`rendered ${outFile} (${dur.toFixed(1)} s of lesson) in ${((Date.now() - t0) / 1000).toFixed(1)} s`);
