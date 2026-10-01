/**
 * Pose-landmark exercise tracking for elbow & shoulder rehabilitation.
 *
 * Consumes MediaPipe PoseLandmarker output (33 normalized landmarks) and
 * produces rep counts / holds + real-time coaching state using the SAME
 * generic RepTracker phase machine as hand tracking. Pure functions —
 * unit-testable, no DOM/camera dependencies.
 */
import { RepTracker, type DetectorConfig, type TrackerState } from "./handTracking";

export interface PoseLandmark {
  x: number;
  y: number;
  z: number;
  visibility?: number;
}

// MediaPipe BlazePose indices used by RehabX
export const L_SHOULDER = 11;
export const R_SHOULDER = 12;
export const L_ELBOW = 13;
export const R_ELBOW = 14;
export const L_WRIST = 15;
export const R_WRIST = 16;
export const L_HIP = 23;
export const R_HIP = 24;

function dist(a: PoseLandmark, b: PoseLandmark): number {
  return Math.hypot(a.x - b.x, a.y - b.y);
}

/** Angle at vertex b formed by segments b→a and b→c, in degrees. */
function angleAt(a: PoseLandmark, b: PoseLandmark, c: PoseLandmark): number {
  const v1x = a.x - b.x;
  const v1y = a.y - b.y;
  const v2x = c.x - b.x;
  const v2y = c.y - b.y;
  const dot = v1x * v2x + v1y * v2y;
  const mag = Math.hypot(v1x, v1y) * Math.hypot(v2x, v2y);
  if (mag < 1e-6) return 180;
  return (Math.acos(Math.max(-1, Math.min(1, dot / mag))) * 180) / Math.PI;
}

/** Pick the arm to track: highest visible elbow+wrist confidence wins. */
function chooseSide(lm: PoseLandmark[]): {
  shoulder: PoseLandmark;
  elbow: PoseLandmark;
  wrist: PoseLandmark;
  hip: PoseLandmark;
} {
  const lScore = (lm[L_ELBOW].visibility ?? 1) + (lm[L_WRIST].visibility ?? 1);
  const rScore = (lm[R_ELBOW].visibility ?? 1) + (lm[R_WRIST].visibility ?? 1);
  const left = lScore >= rScore;
  return {
    shoulder: lm[left ? L_SHOULDER : R_SHOULDER],
    elbow: lm[left ? L_ELBOW : R_ELBOW],
    wrist: lm[left ? L_WRIST : R_WRIST],
    hip: lm[left ? L_HIP : R_HIP],
  };
}

/**
 * One normalized frame of arm metrics. Angles are screen-plane estimates:
 * honest approximations from a front-facing camera, not clinical goniometry.
 */
export interface PoseFrameMetrics {
  /** three-point angle at the elbow (180 = fully straight) */
  elbowAngleDeg: number;
  /** elevation of the upper arm above "hanging down" (0 = down … 180 = overhead) */
  elevationDeg: number;
  /** wrist distance to the OPPOSITE shoulder / torso length (small = crossed body) */
  crossBodyRatio: number;
  /** wrist distance to same-side hip / torso length (small = behind back) */
  behindRatio: number;
  /** how far the wrist rises ABOVE the elbow / torso length (external rotation proxy) */
  erRise: number;
  /** shoulder→elbow segment length / torso length (small = foreshortened toward camera) */
  upperArmRatio: number;
  /** |wrist.x - shoulder.x| / torso length (pendulum swing proxy) */
  swingRatio: number;
  /**
   * Wrist flexion/extension angle from FUSING pose wrist with the hand's
   * middle knuckle (hand+pose mode only; null when no hand detected).
   * 180° = straight forearm-hand line.
   */
  wristFlexExtDeg: number | null;
  /** left-vs-right elevation difference in degrees (symmetry check) */
  symmetryDiffDeg: number | null;
  /** shoulder-blade squeeze amount from ScapMonitor (attached by the coach) */
  scapSqueeze?: number;
}

function elevationOf(shoulder: PoseLandmark, elbow: PoseLandmark): number {
  // 0° when the upper arm hangs down, 90° horizontal, approaching 180° overhead.
  // atan2 alone spans only -90..+90 (vx is an absolute distance); shifting by
  // +90 maps hang→0, horizontal→90, straight-up→180 as the detectors expect.
  const vx = Math.abs(elbow.x - shoulder.x);
  const vy = elbow.y - shoulder.y; // positive = pointing DOWN on screen
  return (Math.atan2(-vy, vx) * 180) / Math.PI + 90;
}

export function computePoseMetrics(
  lm: PoseLandmark[],
  handLm?: { x: number; y: number }[] | null
): PoseFrameMetrics | null {
  if (!lm || lm.length < 25) return null;
  const arm = chooseSide(lm);

  const lSho = lm[L_SHOULDER];
  const rSho = lm[R_SHOULDER];
  const lHip = lm[L_HIP];
  const rHip = lm[R_HIP];
  const shoulderMidX = (lSho.x + rSho.x) / 2;
  const shoulderMidY = (lSho.y + rSho.y) / 2;
  const hipMidY = (lHip.y + rHip.y) / 2;
  const torso = Math.max(1e-6, Math.hypot(shoulderMidX - (lHip.x + rHip.x) / 2, hipMidY - shoulderMidY));

  const oppositeShoulder = arm.shoulder === lSho ? rSho : lSho;
  const elevation = elevationOf(arm.shoulder, arm.elbow);

  let wristFlexExtDeg: number | null = null;
  if (handLm && handLm.length >= 9) {
    const mcp = handLm[9];
    // angle at pose-wrist between forearm direction and hand direction
    wristFlexExtDeg = angleAt(
      { x: arm.elbow.x, y: arm.elbow.y, z: 0 },
      { x: arm.wrist.x, y: arm.wrist.y, z: 0 },
      { x: mcp.x, y: mcp.y, z: 0 },
    );
  }

  const elevL = elevationOf(lSho, lm[L_ELBOW]);
  const elevR = elevationOf(rSho, lm[R_ELBOW]);
  const bothArmsVisible =
    (lm[L_ELBOW].visibility ?? 1) > 0.5 &&
    (lm[R_ELBOW].visibility ?? 1) > 0.5;

  return {
    elbowAngleDeg: angleAt(arm.shoulder, arm.elbow, arm.wrist),
    elevationDeg: elevation,
    crossBodyRatio: dist(arm.wrist, oppositeShoulder) / torso,
    behindRatio: dist(arm.wrist, arm.hip) / torso,
    erRise: ((arm.elbow.y - arm.wrist.y) / torso),
    upperArmRatio: dist(arm.shoulder, arm.elbow) / torso,
    swingRatio: Math.abs(arm.wrist.x - arm.shoulder.x) / torso,
    wristFlexExtDeg,
    symmetryDiffDeg: bothArmsVisible ? Math.abs(elevL - elevR) : null,
  };
}

// ---------------------------------------------------------------------------
// Rep detection — same phase machine as hand tracking
// ---------------------------------------------------------------------------

const POSE_DETECTORS: Record<string, DetectorConfig<PoseFrameMetrics>> = {
  elbow_rom: {
    value: (m) => m.elbowAngleDeg,
    lowEnter: 85,
    lowExit: 148,
    labels: ["Bend the elbow", "Straighten fully"],
    unitHint: "flex",
  },
  shoulder_elev: {
    value: (m) => -m.elevationDeg,
    lowEnter: -95,
    lowExit: -28,
    minFrames: 4,
    labels: ["Raise your arm", "Lower with control"],
    unitHint: "raise",
  },
  light_raise: {
    value: (m) => -m.elevationDeg,
    lowEnter: -85,
    lowExit: -30,
    minFrames: 4,
    labels: ["Raise to shoulder height", "Lower slowly"],
    unitHint: "raise",
  },
  front_raise: {
    value: (m) => -m.elevationDeg,
    lowEnter: -88,
    lowExit: -26,
    minFrames: 4,
    labels: ["Raise forward", "Lower slowly"],
    unitHint: "raise",
  },
  side_raise: {
    value: (m) => -m.elevationDeg,
    lowEnter: -82,
    lowExit: -24,
    minFrames: 4,
    labels: ["Raise out to the side", "Lower slowly"],
    unitHint: "raise",
  },
  wall_slides: {
    value: (m) => -m.elevationDeg,
    lowEnter: -100,
    lowExit: -40,
    minFrames: 6,
    labels: ["Slide up the wall", "Slide back down"],
    unitHint: "slide",
  },
  shoulder_circumduct: {
    value: (m) => -m.elevationDeg,
    lowEnter: -70,
    lowExit: -14,
    minFrames: 6,
    labels: ["Keep circling smoothly", "Circle the other way"],
    unitHint: "circle",
  },
  shoulder_abduct: {
    value: (m) => -m.elevationDeg,
    lowEnter: -80,
    lowExit: -22,
    minFrames: 4,
    labels: ["Lift out to the side", "Bring it back down"],
    unitHint: "abduct",
  },
  shoulder_extension: {
    value: (m) => -m.upperArmRatio,
    lowEnter: -0.52,
    lowExit: -0.68,
    minFrames: 4,
    labels: ["Take your arm gently back", "Return to your side"],
    unitHint: "extend",
  },
  shoulder_crossbody: {
    value: (m) => m.crossBodyRatio,
    lowEnter: 0.55,
    lowExit: 1.0,
    minFrames: 3,
    labels: ["Sweep across your chest", "Return to the start"],
    unitHint: "sweep",
  },
  shoulder_behind: {
    value: (m) => m.behindRatio,
    lowEnter: 0.55,
    lowExit: 0.92,
    minFrames: 3,
    labels: ["Reach gently behind you", "Bring the hand back"],
    unitHint: "reach",
  },
  forearm_er: {
    value: (m) => -m.erRise,
    lowEnter: -0.32,
    lowExit: -0.05,
    minFrames: 4,
    labels: ["Rotate outward", "Return to your ribs"],
    unitHint: "rotate",
  },
  shoulder_pendulum: {
    value: (m) => -m.swingRatio,
    lowEnter: -0.35,
    lowExit: -0.08,
    minFrames: 5,
    labels: ["Let the arm swing", "Keep it relaxed and slow"],
    unitHint: "swing",
  },
  scapular_squeeze: {
    value: (m) => -(m.scapSqueeze ?? 0),
    lowEnter: -0.035,
    lowExit: -0.008,
    minFrames: 4,
    labels: ["Draw the blades together", "Relax fully"],
    unitHint: "squeeze",
  },
  wrist_rom: {
    value: (m) => -(m.wristFlexExtDeg !== null ? Math.abs(m.wristFlexExtDeg - 180) : 0),
    lowEnter: -30,
    lowExit: -10,
    minFrames: 4,
    labels: ["Move through the arc", "Return smoothly"],
    unitHint: "move",
  },
};

/** Movements counted as sustained HOLDS rather than up-down repetitions. */
const HOLD_CONFIGS: Record<
  string,
  { zone: [number, number]; holdMs: number; metric: string; label: string }
> = {
  wrist_stretch_hold: { zone: [-95, -18], holdMs: 8000, metric: "__stretchDev", label: "Hold the stretch" },
  forearm_stretch_hold: { zone: [150, 190], holdMs: 8000, metric: "elbowAngleDeg", label: "Keep the arm straight" },
  elbow_extension_hold: { zone: [150, 190], holdMs: 8000, metric: "elbowAngleDeg", label: "Hold the arm straight" },
  elbow_flexion_hold: { zone: [30, 90], holdMs: 8000, metric: "elbowAngleDeg", label: "Keep the elbow bent" },
  crossbody_stretch_hold: { zone: [0, 0.62], holdMs: 9000, metric: "crossBodyRatio", label: "Hold across the chest" },
  doorway_stretch_hold: { zone: [55, 110], holdMs: 9000, metric: "elevationDeg", label: "Hold the open position" },
  sleeper_stretch_hold: { zone: [0, 0.55], holdMs: 8000, metric: "behindRatio", label: "Hold the gentle press" },
  overhead_stretch_hold: { zone: [135, 185], holdMs: 7000, metric: "elevationDeg", label: "Hold the overhead reach" },
  iso_flexion_hold: { zone: [38, 78], holdMs: 6000, metric: "elevationDeg", label: "Hold the press" },
  iso_extension_hold: { zone: [0, 0.52], holdMs: 6000, metric: "upperArmRatio", label: "Hold the press" },
};

export interface HoldState {
  holds: number;
  holding: boolean;
  /** 0..1 progress through the current required hold duration */
  progress: number;
  targetLabel: string;
  feedback: string[];
}

/** Counts a rep every time the metric stays inside the target zone long enough. */
export class HoldTracker {
  private cfg: (typeof HOLD_CONFIGS)[string];
  private holds = 0;
  private zoneSince: number | null = null;
  readonly isHold = true as const;

  constructor(movementType: string) {
    this.cfg = HOLD_CONFIGS[movementType] ?? HOLD_CONFIGS.forearm_stretch_hold;
  }

  get targetLabel(): string {
    return this.cfg.label;
  }

  update(metrics: PoseFrameMetrics, nowMs: number): HoldState {
    let value: number;
    if (this.cfg.metric === "__stretchDev") {
      value =
        metrics.wristFlexExtDeg !== null ? -Math.abs(metrics.wristFlexExtDeg - 180) : 0;
    } else if (this.cfg.metric === "scapSqueeze") {
      value = -(metrics.scapSqueeze ?? 0);
    } else {
      value = (metrics[this.cfg.metric as keyof PoseFrameMetrics] as unknown as number) ?? 0;
    }
    const [lo, hi] = this.cfg.zone;
    const inZone = value >= lo && value <= hi;
    const feedback: string[] = [];

    if (!inZone) {
      this.zoneSince = null;
      return {
        holds: this.holds,
        holding: false,
        progress: 0,
        targetLabel: this.targetLabel,
        feedback: [`Move into the ${this.cfg.label.toLowerCase()} zone`],
      };
    }
    if (this.zoneSince === null) this.zoneSince = nowMs;
    const held = nowMs - this.zoneSince;
    const progress = Math.max(0, Math.min(1, held / this.cfg.holdMs));
    if (held >= this.cfg.holdMs) {
      this.holds += 1;
      this.zoneSince = nowMs; // require a fresh entry into the zone next time
      feedback.push("Good hold");
    }
    return {
      holds: this.holds,
      holding: held > 400,
      progress,
      targetLabel: this.targetLabel,
      feedback,
    };
  }

  /** Adapter so LiveCoach can treat holds exactly like reps. */
  static toTrackerState(h: HoldState): TrackerState {
    return {
      reps: h.holds,
      phase: h.progress > 0.05 ? "a" : "b",
      rangeScore: h.holding ? 0.8 : 0.35,
      feedback: h.feedback,
      lastRepMs: null,
    };
  }
}

/**
 * Rolling baseline of shoulder width for scapular-squeeze detection:
 * squeezing the blades together narrows the projected shoulder distance.
 */
export class ScapMonitor {
  private widths: number[] = [];
  private baseline: number | null = null;

  reset(): void {
    this.widths = [];
    this.baseline = null;
  }

  /** Squeeze amount 0..~0.15 relative to the learned relaxed baseline. */
  push(lm: PoseLandmark[]): number {
    const w = dist(lm[L_SHOULDER], lm[R_SHOULDER]);
    if (!Number.isFinite(w) || w <= 0) return 0;
    this.widths.push(w);
    if (this.widths.length <= 45) {
      // still learning the relaxed posture — report zero squeeze
      if (this.widths.length === 45) {
        this.baseline = Math.max(...this.widths.slice(-45));
      }
      return 0;
    }
    if (this.baseline === null) this.baseline = Math.max(...this.widths.slice(-45));
    const recentMax = Math.max(...this.widths.slice(-10));
    if (recentMax > this.baseline) this.baseline = recentMax; // re-zero when user relaxes wider
    return Math.max(0, (this.baseline - w) / this.baseline);
  }
}

/** True when the movement type is hold-based rather than rep-based. */
export function isHoldMovement(movementType: string): boolean {
  return movementType in HOLD_CONFIGS || movementType.endsWith("_hold");
}

/**
 * Build the right tracker for a pose-tracked exercise: HoldTracker for
 * stretches/isometrics, otherwise the shared RepTracker with pose thresholds.
 */
export function makePoseTracker(
  movementType: string
): HoldTracker | RepTracker<PoseFrameMetrics> {
  if (isHoldMovement(movementType)) return new HoldTracker(movementType);
  return new RepTracker<PoseFrameMetrics>(
    POSE_DETECTORS[movementType] ?? POSE_DETECTORS.shoulder_elev
  );
}
