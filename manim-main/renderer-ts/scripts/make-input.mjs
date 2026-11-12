// Build render_input.json (version 1) for one chapter from a lessonforge lesson folder.
//   node scripts/make-input.mjs <lesson_dir> <chapter_id> <out.json> [width height fps]
import fs from 'node:fs';
import path from 'node:path';

const [dir, chap, out, w = '1280', h = '720', fps = '30'] = process.argv.slice(2);
const lesson = JSON.parse(fs.readFileSync(path.join(dir, 'lesson.json'), 'utf8'));
const timeline = JSON.parse(fs.readFileSync(path.join(dir, 'timeline.json'), 'utf8'));
const chapter = lesson.chapters.find(c => String(c.id) === String(chap));
if (!chapter) throw new Error(`no chapter ${chap}`);
const ids = new Set(chapter.beats.map(b => b.id));
const input = {
  version: 1,
  title: lesson.title,
  chapter: {id: chapter.id, title: chapter.title, beats: chapter.beats},
  timeline: timeline.filter(t => ids.has(t.id)),
  audio: path.resolve(dir, 'audio', 'narration.wav'),
  width: +w, height: +h, fps: +fps,
};
fs.writeFileSync(out, JSON.stringify(input, null, 1));
console.log(`${out}: chapter ${chapter.id}, ${input.timeline.length} beats`);
