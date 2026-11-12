import assert from 'node:assert/strict';
import {test} from 'node:test';
import {stepTimes, whenSaid} from '../src/timing.ts';

const beat = {id: '01', start: 0, duration: 15.5, sentences: [
  {text: 'The wall is three metres high and the foot of the ladder is four metres out.', start: 1.5, duration: 6.4},
  {text: 'How long is the ladder?', start: 7.9, duration: 2.0},
]};

test('a step appears when its words are said', () => {
  const t = whenSaid('four metres out', beat.sentences)!;
  assert.ok(t > 1.5 + 6.4 * 0.7 && t < 1.5 + 6.4, `got ${t}`);
  assert.equal(whenSaid('How long is the ladder', beat.sentences), 7.9);
  assert.equal(whenSaid('a hippo', beat.sentences), null);
});

test('steps keep their order and unsaid steps are spread through the speech', () => {
  const steps = [{say: 'three metres high'}, {say: 'four metres out'}, {say: 'never said'}];
  const [a, b, c] = stepTimes(steps, beat);
  assert.ok(a < b && b <= c && c < 10, `${a} ${b} ${c}`);
});
