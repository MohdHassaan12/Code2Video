// Web player: a plain <video> so the WebVTT captions load as a text track.
//
// The captions are NOT drawn on the picture while the video is in the page: the track is
// loaded but hidden, and the words being spoken are handed to the page (`onCaption`), which
// shows them under the video. A lesson's frame no longer keeps a band free for them, so the
// browser's own would lie over the foot of the picture. In full screen the page's line
// cannot be seen, and there the browser draws them, as on any video.
import { createElement, forwardRef, useEffect, useImperativeHandle, useRef } from 'react';

import { captionAt, captionPieces, plainCue } from './captions';

export type PlayerHandle = {
  // Jump there and keep playing (the chapter chips).
  seek: (seconds: number) => void;
  // Jump there, playing or paused as it was (a watch mode skipping what it leaves out).
  moveTo: (seconds: number) => void;
  play: () => void;
  pause: () => void;
  // Something is about to be drawn over the video: it must be in the page to be seen.
  leaveFullscreen: () => void;
};
export type PlayerProps = {
  uri: string;
  captionsUri?: string | null;
  // false: captions are off, in the page and in full screen.
  captions?: boolean;
  // The longest caption the page's line has room for; a longer sentence comes in pieces.
  captionChars?: number;
  // The words being spoken now ('' between sentences and in full screen), for a page that
  // shows captions itself. A player that draws them on the picture never calls it.
  onCaption?: (text: string) => void;
  // About four times a second while playing, and on every pause, resume and seek.
  // `seeked`: the position was moved by hand, not reached by playing.
  // `duration`: the length of the video, 0 until it is known.
  onTime?: (seconds: number, seeked: boolean, duration: number) => void;
  // Hide the transport controls while something covers the video.
  locked?: boolean;
  // A lesson whose narration is the learner's own device (voice `browser:<language>`; its video is silent): each
  // caption is read aloud in this language by the browser's own voice as it comes.
  speak?: string | null;
};

const TICK_MS = 250;

function resume(video: HTMLVideoElement): void {
  // A play() cut short by a pause rejects; that is not an error anyone needs to hear.
  Promise.resolve(video.play()).catch(() => {});
}

type FullscreenVideo = HTMLVideoElement & { webkitDisplayingFullscreen?: boolean; webkitExitFullscreen?: () => void };

function inFullscreen(video: FullscreenVideo): boolean {
  return (typeof document !== 'undefined' && document.fullscreenElement === video) || !!video.webkitDisplayingFullscreen; // the second: iPhone Safari
}

function captionTrack(video: HTMLVideoElement): TextTrack | null {
  for (let i = 0; i < video.textTracks.length; i += 1) {
    const track = video.textTracks[i];
    if (track.kind === 'captions' || track.kind === 'subtitles') return track;
  }
  return null;
}

export const Player = forwardRef<PlayerHandle, PlayerProps>(function Player(
  { uri, captionsUri, captions = true, captionChars, onCaption, onTime, locked, speak },
  ref,
) {
  const element = useRef<HTMLVideoElement | null>(null);
  const listener = useRef(onTime);
  useEffect(() => {
    listener.current = onTime;
  }, [onTime]);
  // Works out the caption for this moment; called with every time report (a long sentence
  // is shown in pieces, and a piece changes between two cues).
  const sayCaption = useRef<() => void>(() => {});
  const captionListener = useRef(onCaption);
  useEffect(() => {
    captionListener.current = onCaption;
  }, [onCaption]);
  const room = useRef(captionChars);
  useEffect(() => {
    room.current = captionChars;
    sayCaption.current();
  }, [captionChars]);

  useImperativeHandle(
    ref,
    () => ({
      seek: (seconds: number) => {
        if (!element.current) return;
        element.current.currentTime = seconds;
        resume(element.current);
      },
      moveTo: (seconds: number) => {
        if (element.current) element.current.currentTime = seconds;
      },
      play: () => {
        if (element.current) resume(element.current);
      },
      pause: () => element.current?.pause(),
      leaveFullscreen: () => {
        const video = element.current as FullscreenVideo | null;
        if (!video || typeof document === 'undefined') return;
        try {
          if (document.fullscreenElement === video) Promise.resolve(document.exitFullscreen()).catch(() => {});
          else if (video.webkitDisplayingFullscreen) video.webkitExitFullscreen?.(); // iPhone Safari
          if (document.pictureInPictureElement === video) Promise.resolve(document.exitPictureInPicture()).catch(() => {});
        } catch {
          // A browser without these: the video is simply left where it is.
        }
      },
    }),
    [],
  );

  // Time reports. `timeupdate` alone is too uneven across browsers, so a timer runs
  // alongside it while the video plays, and only then.
  useEffect(() => {
    const video = element.current;
    if (!video) return;
    let moved = false;
    let told = -1;
    let timer: ReturnType<typeof setInterval> | undefined;
    const report = () => {
      const now = video.currentTime;
      const seeked = moved || video.seeking;
      if (now === told && !seeked) return;
      told = now;
      moved = false;
      sayCaption.current();
      listener.current?.(now, seeked, Number.isFinite(video.duration) ? video.duration : 0);
    };
    const onSeeking = () => {
      moved = true;
    };
    const start = () => {
      if (timer === undefined) timer = setInterval(report, TICK_MS);
      report();
    };
    const stop = () => {
      if (timer !== undefined) clearInterval(timer);
      timer = undefined;
      report();
    };
    video.addEventListener('seeking', onSeeking);
    video.addEventListener('seeked', report);
    video.addEventListener('timeupdate', report);
    video.addEventListener('playing', start);
    video.addEventListener('pause', stop);
    video.addEventListener('ended', stop);
    return () => {
      if (timer !== undefined) clearInterval(timer);
      video.removeEventListener('seeking', onSeeking);
      video.removeEventListener('seeked', report);
      video.removeEventListener('timeupdate', report);
      video.removeEventListener('playing', start);
      video.removeEventListener('pause', stop);
      video.removeEventListener('ended', stop);
    };
  }, []);

  // Who draws the captions. In the page: nobody on the picture (the track is 'hidden', which
  // still loads it and still says which cue is active). In full screen: the browser.
  useEffect(() => {
    const video = element.current as FullscreenVideo | null;
    if (!video || !captionsUri) return;
    let shown = '';
    const say = () => {
      const track = captionTrack(video);
      const cues = track && track.mode !== 'disabled' ? track.activeCues : null;
      const cue = cues && cues.length > 0 ? (cues[cues.length - 1] as VTTCue) : null;
      let text = '';
      if (cue && captions && !inFullscreen(video)) {
        const span = cue.endTime - cue.startTime;
        text = captionAt(captionPieces(plainCue(cue.text), room.current), span > 0 ? (video.currentTime - cue.startTime) / span : 0);
      }
      if (text === shown) return;
      shown = text;
      captionListener.current?.(text);
    };
    const settle = () => {
      const track = captionTrack(video);
      if (track) {
        // Captions off: 'disabled', unless the device reads them aloud, which needs the track's cues ('hidden').
        const mode: TextTrackMode = !captions ? (speak ? 'hidden' : 'disabled') : inFullscreen(video) ? 'showing' : 'hidden';
        if (track.mode !== mode) track.mode = mode;
        track.oncuechange = say;
      }
      say();
    };
    // The browser's own captions menu was used. In the page that must not put them back on
    // the picture; in full screen it is the viewer's choice and is left alone.
    const onChange = () => {
      if (inFullscreen(video)) say();
      else settle();
    };
    sayCaption.current = say;
    settle();
    const tracks = video.textTracks;
    tracks.addEventListener('addtrack', settle);
    tracks.addEventListener('change', onChange);
    video.addEventListener('loadedmetadata', settle);
    video.addEventListener('webkitbeginfullscreen', settle);
    video.addEventListener('webkitendfullscreen', settle);
    if (typeof document !== 'undefined') document.addEventListener('fullscreenchange', settle);
    return () => {
      sayCaption.current = () => {};
      tracks.removeEventListener('addtrack', settle);
      tracks.removeEventListener('change', onChange);
      video.removeEventListener('loadedmetadata', settle);
      video.removeEventListener('webkitbeginfullscreen', settle);
      video.removeEventListener('webkitendfullscreen', settle);
      if (typeof document !== 'undefined') document.removeEventListener('fullscreenchange', settle);
      const track = captionTrack(video);
      if (track) track.oncuechange = null;
      if (shown) captionListener.current?.('');
    };
  }, [captionsUri, captions, speak]);

  // The learner's device reads each caption aloud as it comes (a lesson narrated with the device voice). A pause or a
  // jump stops the reading; playing again reads the caption of that moment from its start.
  useEffect(() => {
    const video = element.current;
    const synth = typeof window !== 'undefined' ? window.speechSynthesis : undefined;
    if (!video || !captionsUri || !speak || !synth) return;
    let read: TextTrackCue | null = null;
    const voiceFor = () => {
      const all = synth.getVoices();
      return all.find((v) => v.lang === speak) ?? all.find((v) => v.lang.slice(0, 2) === speak.slice(0, 2)) ?? null;
    };
    const readNow = () => {
      const track = captionTrack(video);
      const cues = track ? track.activeCues : null;
      const cue = cues && cues.length > 0 ? cues[cues.length - 1] : null;
      if (!cue || cue === read || video.paused || video.seeking) return;
      read = cue;
      synth.cancel();
      const line = new SpeechSynthesisUtterance(plainCue((cue as VTTCue).text));
      line.lang = speak;
      const voice = voiceFor();
      if (voice) line.voice = voice;
      synth.speak(line);
    };
    const stop = () => {
      synth.cancel();
      read = null;
    };
    const timer = setInterval(readNow, TICK_MS);
    video.addEventListener('playing', readNow);
    video.addEventListener('pause', stop);
    video.addEventListener('seeking', stop);
    video.addEventListener('ended', stop);
    return () => {
      clearInterval(timer);
      video.removeEventListener('playing', readNow);
      video.removeEventListener('pause', stop);
      video.removeEventListener('seeking', stop);
      video.removeEventListener('ended', stop);
      synth.cancel();
    };
  }, [captionsUri, speak]);

  return createElement(
    'video',
    {
      ref: element,
      controls: !locked,
      preload: 'metadata',
      crossOrigin: 'anonymous',
      style: { display: 'block', width: '100%', aspectRatio: '16 / 9', background: '#000', borderRadius: 12 },
    },
    createElement('source', { src: uri, type: 'video/mp4' }),
    // No `default`: a default track is drawn on the picture before any script can hide it.
    captionsUri ? createElement('track', { kind: 'captions', src: captionsUri, label: 'Captions' }) : null,
  );
});
