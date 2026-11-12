// Render one chapter: node scripts/render.mjs <render_input.json> <out.mp4>
// Revideo 0.11 sometimes dies at start-up with "The thread is not available in the current context"
// (about 1 run in 4 here); a fresh process then works, so each attempt runs in its own process.
import {spawnSync} from 'node:child_process';
import path from 'node:path';

const once = path.join(path.dirname(new URL(import.meta.url).pathname), 'render-once.mjs');
const tries = Number(process.env.RENDER_TRIES || 3);
for (let i = 1; i <= tries; i++) {
  const r = spawnSync(process.execPath, [once, ...process.argv.slice(2)], {stdio: 'inherit'});
  if (r.status === 0) process.exit(0);
  console.error(`[render] attempt ${i} of ${tries} failed (exit ${r.status})`);
}
process.exit(1);
