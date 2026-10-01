"use client";

import { useCallback, useRef, useState } from "react";

/**
 * Reusable exercise tutorial player.
 *
 * Plays the per-exercise tutorial video (`/tutorials/<slug>.mp4`) with simple
 * play/pause/replay controls and a looping demo. If the video is missing or
 * fails to load, it degrades gracefully to a "Tutorial unavailable" card —
 * the session itself never depends on this component succeeding.
 */
export default function ExerciseTutorial({
  src,
  slug,
  label,
  autoPlay = true,
}: {
  src: string;
  slug: string;
  label?: string;
  autoPlay?: boolean;
}) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [failed, setFailed] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [progress, setProgress] = useState(0);
  const [prevSrc, setPrevSrc] = useState(src);

  // dynamic tutorials: reset state whenever the selected exercise changes
  // (adjust-during-render pattern — no cascading effect render)
  if (prevSrc !== src) {
    setPrevSrc(src);
    setFailed(false);
    setPlaying(false);
    setProgress(0);
  }

  const toggle = useCallback(() => {
    const v = videoRef.current;
    if (!v) return;
    if (v.paused || v.ended) {
      v.play().catch(() => undefined);
    } else {
      v.pause();
    }
  }, []);

  const replay = useCallback(() => {
    const v = videoRef.current;
    if (!v) return;
    v.currentTime = 0;
    v.play().catch(() => undefined);
  }, []);

  const seek = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    const v = videoRef.current;
    if (!v || !v.duration) return;
    const rect = e.currentTarget.getBoundingClientRect();
    v.currentTime = ((e.clientX - rect.left) / rect.width) * v.duration;
  }, []);

  if (failed) {
    return (
      <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-slate-300 bg-slate-50 px-4 py-8 text-center">
        <span className="rounded-full bg-amber-100 px-3 py-1 text-xs font-semibold text-amber-800">
          ⚠ Tutorial unavailable
        </span>
        <p className="mt-2 text-sm text-slate-500">
          The video could not be loaded{label ? ` for ${label}` : ""} — follow the written
          steps below. Your session continues normally.
        </p>
        {/* lightweight animated fallback keyed to the same slug */}
        <img
          src={`/animations/${slug}.svg`}
          alt=""
          aria-hidden
          className="mt-3 h-24 opacity-40"
          onError={(e) => {
            e.currentTarget.style.display = "none";
          }}
        />
      </div>
    );
  }

  return (
    <div className="group relative overflow-hidden rounded-xl bg-slate-900 shadow-inner">
      <video
        ref={videoRef}
        src={src}
        className="block aspect-video w-full cursor-pointer object-cover"
        autoPlay={autoPlay}
        loop
        muted
        playsInline
        preload="metadata"
        onClick={toggle}
        onPlay={() => setPlaying(true)}
        onPause={() => setPlaying(false)}
        onTimeUpdate={(e) => {
          const v = e.currentTarget;
          if (v.duration) setProgress((v.currentTime / v.duration) * 100);
        }}
        onError={() => setFailed(true)}
      />
      {!playing && (
        <button
          type="button"
          onClick={toggle}
          aria-label="Play tutorial"
          className="absolute inset-0 flex items-center justify-center bg-black/25 transition-colors hover:bg-black/35"
        >
          <span className="flex h-14 w-14 items-center justify-center rounded-full bg-white/95 text-xl text-teal-700 shadow-lg">
            ▶
          </span>
        </button>
      )}
      {/* custom control bar */}
      <div className="absolute inset-x-0 bottom-0 flex items-center gap-3 bg-gradient-to-t from-black/70 to-transparent px-3 pb-2 pt-6">
        <button
          type="button"
          onClick={toggle}
          aria-label={playing ? "Pause" : "Play"}
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-white/15 text-sm text-white backdrop-blur hover:bg-white/30"
        >
          {playing ? "❚❚" : "▶"}
        </button>
        <div
          role="slider"
          aria-label="Seek tutorial"
          aria-valuenow={Math.round(progress)}
          tabIndex={0}
          onClick={seek}
          className="h-1.5 flex-1 cursor-pointer overflow-hidden rounded-full bg-white/20"
        >
          <div className="h-full rounded-full bg-teal-400" style={{ width: `${progress}%` }} />
        </div>
        <button
          type="button"
          onClick={replay}
          aria-label="Replay tutorial"
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-white/15 text-xs text-white backdrop-blur hover:bg-white/30"
        >
          ↻
        </button>
      </div>
    </div>
  );
}
