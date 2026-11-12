import assert from 'node:assert/strict';
import {test} from 'node:test';
import {parseMathFunction, tickStep} from '../src/figure_math.ts';

test('tickStep computes clean powers of ten steps and decimal precision', () => {
  const [s1, p1] = tickStep(-5, 5);
  assert.equal(s1, 1);
  assert.equal(p1, 0);

  const [s2, p2] = tickStep(0.9, 1.0);
  assert.ok(s2 <= 0.05);
  assert.ok(p2 >= 1);

  const [s3, p3] = tickStep(0, 100);
  assert.equal(s3, 10);
  assert.equal(p3, 0);
});

test('parseMathFunction handles linear and polynomial formulas', () => {
  const f1 = parseMathFunction('2*x - 1');
  assert.ok(f1);
  assert.equal(f1(0), -1);
  assert.equal(f1(3), 5);

  const f2 = parseMathFunction('x^2 + 3');
  assert.ok(f2);
  assert.equal(f2(2), 7);
  assert.equal(f2(-3), 12);
});

test('parseMathFunction handles implicit multiplication and trig/math functions', () => {
  const f = parseMathFunction('2x + 4');
  assert.ok(f);
  assert.equal(f(5), 14);

  const fTrig = parseMathFunction('sin(x)');
  assert.ok(fTrig);
  assert.ok(Math.abs(fTrig(0)) < 1e-6);

  const fSqrt = parseMathFunction('sqrt(x) + 1');
  assert.ok(fSqrt);
  assert.equal(fSqrt(4), 3);
});

test('parseMathFunction safely rejects arbitrary code execution', () => {
  assert.equal(parseMathFunction('process.exit(1)'), null);
  assert.equal(parseMathFunction('fetch("http://example.com")'), null);
  assert.equal(parseMathFunction('while(1){}'), null);
});
