// Math and parsing helpers for code-drawn figure kinds.

export function tickStep(lo: number, hi: number): [number, number] {
  const span = Math.max(hi - lo, 1e-9);
  const power = Math.pow(10, Math.floor(Math.log10(span / 10)));
  let step = power, places = 0;
  for (const m of [1, 2, 5, 10, 20]) {
    step = m * power;
    places = Math.max(0, -Math.floor(Math.log10(step) + 1e-9));
    if (span / step <= (places === 0 ? 12 : 5)) {
      return [step, places];
    }
  }
  return [step, places];
}

const ALLOWED_WORDS = new Set([
  'x', 'sin', 'cos', 'tan', 'sqrt', 'abs', 'exp', 'log', 'pi', 'e',
  'math', 'Math',
]);

export function parseMathFunction(expr: string): ((x: number) => number) | null {
  try {
    let s = expr.trim();
    // Validate characters
    if (!/^[0-9a-zA-Z_+\-*/().,\s^]*$/.test(s)) return null;

    s = s.replace(/\^/g, '**');
    s = s.replace(/\b(?:np|numpy|math)\./gi, '');

    // Check all word tokens are in ALLOWED_WORDS
    const words = s.match(/[a-zA-Z_][a-zA-Z0-9_]*/g) || [];
    if (words.some(w => !ALLOWED_WORDS.has(w) && !ALLOWED_WORDS.has(w.toLowerCase()))) {
      return null;
    }

    // Insert implicit multiplication: 2x -> 2*x, 3(x+1) -> 3*(x+1)
    s = s.replace(/(\d)\s*([a-zA-Z(])/g, '$1*$2');
    s = s.replace(/\)\s*([a-zA-Z(\d])/g, ')*$1');
    s = s.replace(/\bx\s*\(/gi, 'x*(');

    // Replace math functions: sin, cos, tan, sqrt, abs, exp, log, pi, e
    s = s.replace(/\bsin\b/gi, 'Math.sin');
    s = s.replace(/\bcos\b/gi, 'Math.cos');
    s = s.replace(/\btan\b/gi, 'Math.tan');
    s = s.replace(/\bsqrt\b/gi, 'Math.sqrt');
    s = s.replace(/\babs\b/gi, 'Math.abs');
    s = s.replace(/\bexp\b/gi, 'Math.exp');
    s = s.replace(/\blog\b/gi, 'Math.log');
    s = s.replace(/\bpi\b/gi, 'Math.PI');
    s = s.replace(/\be\b/gi, 'Math.E');

    const fn = new Function('x', `"use strict"; return (${s});`) as (x: number) => number;
    const testVal = fn(1);
    if (typeof testVal !== 'number') return null;
    return fn;
  } catch {
    return null;
  }
}
