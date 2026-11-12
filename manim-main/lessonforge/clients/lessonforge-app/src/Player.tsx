// Native player (iOS / Android): expo-video. The web build uses Player.web.tsx.
import { forwardRef, useEffect, useImperativeHandle, useRef } from 'react';
import { StyleSheet } from 'react-native';
import { useEventListener } from 'expo';
import { useVideoPlayer, VideoView } from 'expo-video';

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
  // For the web player, which hands the captions to the page. Here the native controls
  // show the file's own subtitle track, on the picture, and neither is used.
  captions?: boolean;
  captionChars?: number;
  onCaption?: (text: string) => void;
  // About four times a second while playing, and on every pause and resume.
  // `seeked`: the position was moved by hand, not reached by playing.
  // `duration`: the length of the video, 0 until it is known.
  onTime?: (seconds: number, seeked: boolean, duration: number) => void;
  // Hide the transport controls while something covers the video.
  locked?: boolean;
  // A lesson whose narration is the learner's own device (voice `browser:<language>`): the web player reads the
  // captions aloud in this language. Not on phones yet (the native player shows the captions only).
  speak?: string | null;
};

const TICK_S = 0.25;
// The player reports no seeks, so one is inferred: the position moved further than
// playing could have carried it since the last report (or moved at all while paused).
const SEEK_SLACK_S = 0.75;

export const Player = forwardRef<PlayerHandle, PlayerProps>(function Player({ uri, onTime, locked }, ref) {
  // The mp4 carries its own subtitle track and chapter markers, so the native
  // controls expose captions without a sidecar file.
  const player = useVideoPlayer(uri, (created) => {
    created.timeUpdateEventInterval = TICK_S;
  });
  const view = useRef<VideoView>(null);
  const fullscreen = useRef(false);
  const listener = useRef(onTime);
  useEffect(() => {
    listener.current = onTime;
  }, [onTime]);

  const last = useRef({ media: 0, wall: 0, playing: false });
  const report = (now: number, playing: boolean) => {
    const wall = Date.now();
    const moved = now - last.current.media;
    const played = last.current.playing ? ((wall - last.current.wall) / 1000) * (player.playbackRate || 1) : 0;
    last.current = { media: now, wall, playing };
    listener.current?.(now, moved < -SEEK_SLACK_S || moved > played + SEEK_SLACK_S, player.duration > 0 ? player.duration : 0);
  };
  useEventListener(player, 'timeUpdate', ({ currentTime }) => report(currentTime, last.current.playing));
  useEventListener(player, 'playingChange', ({ isPlaying }) => report(player.currentTime, isPlaying));

  useImperativeHandle(
    ref,
    () => ({
      seek: (seconds: number) => {
        player.currentTime = seconds;
        player.play();
      },
      moveTo: (seconds: number) => {
        player.currentTime = seconds;
      },
      play: () => player.play(),
      pause: () => player.pause(),
      leaveFullscreen: () => {
        if (fullscreen.current) view.current?.exitFullscreen().catch(() => {});
      },
    }),
    [player],
  );

  return (
    <VideoView
      ref={view}
      player={player}
      nativeControls={!locked}
      contentFit="contain"
      style={styles.video}
      onFullscreenEnter={() => {
        fullscreen.current = true;
      }}
      onFullscreenExit={() => {
        fullscreen.current = false;
      }}
    />
  );
});

const styles = StyleSheet.create({
  video: { width: '100%', aspectRatio: 16 / 9, backgroundColor: '#000', borderRadius: 12 },
});
