/**
 * Hand-landmark exercise tracking logic.
 *
 * Consumes MediaPipe HandLandmarker output (21 normalized landmarks) and
 * produces rep counts + real-time form feedback for each movement_type in
 * the exercise library. Pure functions — no DOM/camera dependencies.
 */

export interface Landmark {
  x: number;
  y: number;
  z: number;
}

const TIPS = [8, 12, 16, 20]; // index, middle, ring, pinky fingertips
const WRIST = 0;
const MIDDLE_MCP = 9;
const INDEX_MCP = 5;

function dist(a: Landmark, b: Landmark): number {
  return Math.hypot(a.x - b.x, a.y - b.y);
}

/** One normalized frame of metrics derived from the 21 landmarks. */
export interface FrameMetrics {
  /** average openness of the four fingers: ~0.6 curled … ~1.9 extended */
  openness: number;
  /** adjacent fingertip spread / palm size */
  spread: number;
  /** thumb-tip to pinky-tip distance / palm size (small = opposed) */
  thumbPinky: number;
  /** thumb-tip to index-MCP distance / palm size (large = thumb abducted) */
  thumbIndex: number;
  /** palm orientation angle in degrees (rotation proxy) */
  palmAngleDeg: number;
  /** fingertip centroid height relative to wrist (flex/ext proxy) */
  tipHeight: number;
  /** normalized vertical position of the wrist (small = hand raised) */
  wristY: number;
}

export function computeMetrics(lm: Landmark[]): FrameMetrics | null {
  if (!lm || lm.length < 21) return null;
  const wrist = lm[WRIST];
  const palm = dist(wrist, lm[MIDDLE_MCP]);
  if (palm < 1e-6) return null;

  const openness =
    TIPS.reduce((acc, i) => acc + dist(lm[i], wrist) / palm, 0) / TIPS.length;
  let spread = 0;
  for (let k = 0; k < TIPS.length - 1; k++) spread += dist(lm[TIPS[k]], lm[TIPS[k + 1]]);
  spread = spread / (TIPS.length - 1) / palm;

  const thumbPinky = dist(lm[4], lm[20]) / palm;
  const thumbIndex = dist(lm[4], lm[INDEX_MCP]) / palm;
  const angle = (Math.atan2(lm[MIDDLE_MCP].y - wrist.y, lm[MIDDLE_MCP].x - wrist.x) * 180) / Math.PI;
  const tipY = TIPS.reduce((acc, i) => acc + lm[i].y, 0) / TIPS.length;
  return {
    openness,
    spread,
    thumbPinky,
    thumbIndex,
    palmAngleDeg: angle,
    tipHeight: (tipY - wrist.y) / palm,
    wristY: wrist.y,
  };
}

// ---------------------------------------------------------------------------
// Rep detection
// ---------------------------------------------------------------------------

type Phase = "a" | "b";

/**
 * One rep-counting rule shared by BOTH hand and pose trackers. Generic over
 * the frame-metrics type so the same phase machine drives every exercise:
 * the metric extractor pulls a single number and the hysteresis thresholds
 * decide when a repetition's extremes were reached.
 */
export interface DetectorConfig<M = FrameMetrics> {
  /** metric extractor */
  value: (m: M) => number;
  /** thresholds with hysteresis: below/above switches phase */
  lowEnter: number;
  lowExit: number;
  /** minimum frames a phase must be held to count */
  minFrames?: number;
  labels: [string, string];
  unitHint?: string;
}

const DETECTORS: Record<string, DetectorConfig> = {
  flexion: {
    value: (m) => m.openness,
    lowEnter: 1.05,
    lowExit: 1.35,
    labels: ["Make a fist", "Open the hand"],
    unitHint: "curl",
  },
  extension: {
    value: (m) => m.openness,
    lowEnter: 1.15,
    lowExit: 1.5,
    labels: ["Bend fingers", "Straighten fully"],
    unitHint: "extend",
  },
  combined_flexion: {
    value: (m) => m.openness,
    lowEnter: 1.1,
    lowExit: 1.4,
    labels: ["Curl fingers", "Open hand"],
    unitHint: "walk",
  },
  combined: {
    value: (m) => m.openness,
    lowEnter: 1.05,
    lowExit: 1.4,
    labels: ["Close the fist", "Open fully"],
    unitHint: "grip",
  },
  isometric_grip: {
    value: (m) => m.openness,
    lowEnter: 1.1,
    lowExit: 1.3,
    labels: ["Squeeze and hold", "Release slowly"],
    unitHint: "hold",
  },
  abduction: {
    value: (m) => m.spread,
    lowEnter: 0.55,
    lowExit: 0.85,
    labels: ["Spread fingers apart", "Bring together"],
    unitHint: "spread",
  },
  opposition: {
    value: (m) => m.thumbPinky,
    lowEnter: 0.45,
    lowExit: 0.85,
    labels: ["Touch pinky with thumb", "Open thumb away"],
    unitHint: "oppose",
  },
  // thumb tip far from the index knuckle = abducted; inverted so the
  // detector's "extreme" stays on the low side of the state machine
  thumb_abduction: {
    value: (m) => -m.thumbIndex,
    lowEnter: -1.3,
    lowExit: -0.85,
    labels: ["Lift the thumb away from the palm", "Bring the thumb back alongside"],
    unitHint: "abduct",
  },
  // hand elevation for elbow work: wristY small = hand raised; inverted so
  // neutral (hand low) is the high side the rep is counted on
  elbow_flexion: {
    value: (m) => m.wristY - 0.5,
    lowEnter: -0.16,
    lowExit: -0.04,
    labels: ["Bend the elbow, hand toward the shoulder", "Lower and straighten the arm"],
    unitHint: "flex",
  },
  rotation: {
    value: (m) => m.palmAngleDeg,
    lowEnter: -18,
    lowExit: 12,
    labels: ["Rotate palm down/out", "Rotate back up"],
    unitHint: "rotate",
  },
  rotation_strength: {
    value: (m) => m.palmAngleDeg,
    lowEnter: -20,
    lowExit: 14,
    labels: ["Twist one way", "Twist the other way"],
    unitHint: "twist",
  },
  deviation: {
    value: (m) => m.tipHeight,
    lowEnter: 0.45,
    lowExit: 0.75,
    labels: ["Tilt toward little finger", "Return to centre"],
    unitHint: "tilt",
  },
};

export interface TrackerState {
  reps: number;
  phase: Phase;
  /** how far into the current target extreme the user got (0..1) */
  rangeScore: number;
  feedback: string[];
  lastRepMs: number[] | null;
}

/** Non-generic view of any rep-counting tracker, whatever metrics it consumes.
 * Class methods are bivariantly assignable, so RepTracker<PoseFrameMetrics>
 * satisfies this interface even though its update() takes a narrower type. */
export interface TrackerLike {
  readonly targetLabel: string;
  update(metrics: unknown, nowMs: number): TrackerState;
}

export class RepTracker<M = FrameMetrics> {
  private cfg: DetectorConfig<M>;
  private phase: Phase = "b";
  private phaseFrames = 0;
  private reps = 0;
  private phaseStart = 0;
  private lastRepDurations: number[] = [];

  constructor(source: string | DetectorConfig<M>) {
    this.cfg =
      typeof source === "string"
        ? ((DETECTORS[source] ?? DETECTORS.combined) as unknown as DetectorConfig<M>)
        : source;
    // start at the neutral side of the cycle
    this.phase = "b";
  }

  get targetLabel(): string {
    return this.phase === "a" ? this.cfg.labels[0] : this.cfg.labels[1];
  }

  update(metrics: M, nowMs: number): TrackerState {
    const v = this.cfg.value(metrics);
    const minFrames = this.cfg.minFrames ?? 4;
    const feedback: string[] = [];

    const inLow = v <= this.cfg.lowEnter;
    const inHigh = v >= this.cfg.lowExit;
    let rangeScore = 0.5;

    const nextPhase: Phase | null =
      this.phase === "b" && inLow ? "a" : this.phase === "a" && inHigh ? "b" : null;

    if (nextPhase === "a") {
      // entering the required extreme: arm the rep, do not count yet
      if (this.phaseFrames >= minFrames) {
        this.phase = "a";
        this.phaseFrames = 0;
        this.phaseStart = nowMs;
      } else {
        // still travelling into the extreme: keep accumulating frames,
        // otherwise a start already inside the zone freezes here forever
        this.phaseFrames += 1;
      }
    } else if (nextPhase === "b") {
      // completing the cycle back to neutral: exactly one rep
      if (this.phaseFrames >= minFrames && this.phaseStart > 0) {
        const duration = nowMs - this.phaseStart;
        this.lastRepDurations.push(duration);
        if (this.lastRepDurations.length > 10) this.lastRepDurations.shift();
        this.reps += 1;
        if (duration < 350) feedback.push("Slow down — move with control");
        this.phaseStart = nowMs;
      }
      this.phase = "b";
      this.phaseFrames = 0;
    } else {
      this.phaseFrames += 1;
      // range score: how deep into the required extreme the user currently is
      const span = Math.abs(this.cfg.lowExit - this.cfg.lowEnter) || 1;
      const mid = (this.cfg.lowEnter + this.cfg.lowExit) / 2;
      const target = this.phase === "a" ? this.cfg.lowEnter - span : this.cfg.lowExit + span;
      rangeScore = Math.max(0, Math.min(1, 1 - Math.abs(target - v) / (2 * span)));
      if (mid === 0) rangeScore = Math.max(rangeScore, 0); // keep valid for angle-based
    }

    if (this.phaseStart > 0 && nowMs - this.phaseStart > 6000) {
      feedback.push("Range poora nahi aa raha — aaram se aur gehraai tak jao");
      this.phaseStart = nowMs; // re-arm so we do not spam every frame
    }

    return {
      reps: this.reps,
      phase: this.phase,
      rangeScore: Number.isFinite(rangeScore) ? rangeScore : 0.5,
      feedback,
      lastRepMs: null,
    };
  }
}

// ---------------------------------------------------------------------------
// Pain-aware dosage (mirrors the rehabilitation engine's intensity rules)
// ---------------------------------------------------------------------------

export function painAdjustedTargets(
  painLevel: number,
  repMax: number,
  setMax: number
): { reps: number; sets: number; intensity: string; warning: string } {
  if (painLevel >= 7) {
    return {
      reps: Math.max(4, Math.ceil(repMax * 0.5)),
      sets: 1,
      intensity: "minimal",
      warning:
        "High pain — minimal intensity only. Stop immediately if pain increases during any movement.",
    };
  }
  if (painLevel >= 3) {
    return {
      reps: Math.ceil(repMax * 0.75),
      sets: Math.min(setMax, 2),
      intensity: "low",
      warning: "Moderate pain — stay within a comfortable, pain-free range.",
    };
  }
  return {
    reps: repMax,
    sets: setMax,
    intensity: "normal",
    warning: "",
  };
}
