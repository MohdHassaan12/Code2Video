// Captions shown by the page, under the video, instead of by the browser on the picture.
// A lesson's frame keeps no band for captions any more (the owner, 2026-10-10): the space
// went to the picture, and under the video the words can be set at a size a phone can read.
//
// A caption file has one cue for each sentence, and a sentence can run to 190 characters:
// five lines on a phone. So a long cue is shown in pieces of at most two lines, each for a
// share of the cue's time that matches its share of the words.

// About 42 characters fit a line on a phone held upright; a caption is two lines.
export const CAPTION_CHARS = 84;
// The page's caption line is set in this size.
export const CAPTION_FONT = 17;
export const CAPTION_LINE = 24;

// How long a caption may be to stand in a line `width` pixels wide: one line when the
// longest caption fits one, else two. A letter of running text is about half its size wide.
export function captionRoom(width: number): { most: number; lines: number } {
  const perLine = Math.floor(width / (CAPTION_FONT * 0.52));
  if (perLine >= CAPTION_CHARS) return { most: CAPTION_CHARS, lines: 1 };
  return { most: Math.max(36, Math.min(CAPTION_CHARS, perLine * 2)), lines: 2 };
}

// A cue's words without its markup (<v Name>, <c.class>, <00:01.000>) and line breaks.
export function plainCue(text: string): string {
  return text
    .replace(/<[^>]*>/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}

// A sentence cut into pieces of about equal length, none longer than `most`: at a comma
// or a full stop where one is near, else at the end of a word. One piece when it fits.
export function captionPieces(text: string, most = CAPTION_CHARS): string[] {
  const words = text.split(' ').filter(Boolean);
  if (text.length <= most || words.length < 2) return text ? [text] : [];
  const share = text.length / Math.ceil(text.length / most);
  const pieces: string[] = [];
  let line = '';
  let left = text.length;
  for (const word of words) {
    const next = line ? `${line} ${word}` : word;
    if (line && next.length > most) {
      pieces.push(line);
      left -= line.length + 1;
      line = word;
      continue;
    }
    line = next;
    const pause = /[,;:.!?…]$/.test(word);
    // Long enough to stand alone, and what is left is more than a word or two.
    if (left - line.length > most * 0.3 && (line.length >= share || (pause && line.length >= share * 0.7))) {
      pieces.push(line);
      left -= line.length + 1;
      line = '';
    }
  }
  if (line) pieces.push(line);
  return pieces;
}

// The piece being spoken when `share` (0 to 1) of the cue's time has passed.
export function captionAt(pieces: string[], share: number): string {
  if (pieces.length === 0) return '';
  const total = pieces.reduce((sum, piece) => sum + piece.length, 0);
  let passed = 0;
  for (const piece of pieces) {
    passed += piece.length;
    if (share * total < passed) return piece;
  }
  return pieces[pieces.length - 1];
}
