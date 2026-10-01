/**
 * Real-time hand-rehab coaching presentation layer.
 *
 * Turns raw tracker state + per-frame metrics into the friendly 🟢🟡🔴
 * feedback shown over the live camera, and accumulates the hand-specific
 * session statistics (form score, ROM estimate, incorrect reps) rendered on
 * the results card. Pure logic — unit-testable, no DOM access.
 */
import type { TrackerState } from "./handTracking";

export type FeedbackLevel = "good" | "warn" | "error";

export interface FeedbackItem {
  level: FeedbackLevel;
  message: string;
}

export const LEVEL_DOT: Record<FeedbackLevel, string> = {
  good: "🟢",
  warn: "🟡",
  error: "🔴",
};

/** Exercises where the wrist must stay straight while fingers/thumb move. */
const STEADY_WRIST = new Set([
  "flexion",
  "extension",
  "combined",
  "combined_flexion",
  "opposition",
  "thumb_abduction",
  "isometric_grip",
]);

export function needsSteadyWrist(movementType: string): boolean {
  return STEADY_WRIST.has(movementType);
}

interface Phrases {
  deeper: string;
  good: string;
}

const PHRASES: Record<string, Phrases> = {
  flexion: { deeper: "Bend your fingers a little more", good: "Good finger movement" },
  extension: { deeper: "Straighten your fingers fully", good: "Good finger extension" },
  combined_flexion: { deeper: "Curl the fingers a little further", good: "Good controlled movement" },
  combined: { deeper: "Close the fist fully before opening", good: "Good fist movement" },
  isometric_grip: { deeper: "Squeeze a little firmer", good: "Good grip hold" },
  abduction: { deeper: "Spread your fingers a little more", good: "Good finger spread" },
  thumb_abduction: { deeper: "Lift the thumb further from the palm", good: "Good thumb movement" },
  opposition: { deeper: "Reach the thumb toward the fingertip", good: "Good thumb opposition" },
  rotation: { deeper: "Rotate a little further", good: "Good rotation" },
  rotation_strength: { deeper: "Twist a little further", good: "Good twisting movement" },
  deviation: { deeper: "Tilt slightly further to the side", good: "Good wrist position" },
  elbow_flexion: { deeper: "Raise your wrist slightly higher", good: "Good elbow movement" },
  // ---- pose-tracked upper-limb movements ----
  elbow_rom: { deeper: "Bend your elbow a little further", good: "Great elbow movement" },
  shoulder_elev: { deeper: "Raise your arm slightly higher", good: "Great shoulder movement" },
  light_raise: { deeper: "Lift to shoulder height", good: "Great controlled raise" },
  front_raise: { deeper: "Raise the arm slightly higher", good: "Good front raise" },
  side_raise: { deeper: "Raise slightly higher to the side", good: "Good side raise" },
  wall_slides: { deeper: "Slide a little further up the wall", good: "Good wall slide" },
  shoulder_circumduct: { deeper: "Make the circles a little fuller", good: "Smooth circling" },
  shoulder_abduct: { deeper: "Lift slightly higher out to the side", good: "Great shoulder lift" },
  shoulder_extension: { deeper: "Take your arm gently further back", good: "Good extension" },
  shoulder_crossbody: { deeper: "Sweep a little further across", good: "Good cross-body sweep" },
  shoulder_behind: { deeper: "Reach gently a little further behind", good: "Good behind-the-back reach" },
  forearm_er: { deeper: "Rotate outward a little further", good: "Good outward rotation" },
  shoulder_pendulum: { deeper: "Let the arm swing a little more", good: "Relaxed swinging — keep going" },
  scapular_squeeze: { deeper: "Draw the shoulder blades together more", good: "Good blade squeeze" },
  wrist_rom: { deeper: "Move through a little more of the arc", good: "Good wrist movement" },
};

function phrasesFor(movementType: string): Phrases {
  return PHRASES[movementType] ?? PHRASES.combined;
}

/**
 * Rolling palm-angle monitor. A rising standard deviation of the palm angle
 * means the whole forearm is swinging instead of staying supported — flagged
 * as an unstable wrist for exercises that need a steady wrist.
 */
export class WristMonitor {
  private angles: number[] = [];

  reset(): void {
    this.angles = [];
  }

  push(angleDeg: number): void {
    this.angles.push(angleDeg);
    if (this.angles.length > 24) this.angles.shift();
  }

  get unstable(): boolean {
    const n = this.angles.length;
    if (n < 12) return false;
    const mean = this.angles.reduce((s, x) => s + x, 0) / n;
    const variance = this.angles.reduce((s, x) => s + (x - mean) ** 2, 0) / n;
    return Math.sqrt(variance) > 7;
  }
}

export interface LiveFeedbackInput {
  /** what the camera should be seeing — "hand" or a body-part label for pose mode */
  handDetected: boolean;
  trackerFeedback: string[];
  targetLabel: string;
  rangeScore: number;
  phase: "a" | "b";
  wristUnstable: boolean;
  steadyWristRequired: boolean;
  movementType: string;
  partLabel?: string;
}

/** One prioritised coaching message for the current frame. */
export function buildLiveFeedback(i: LiveFeedbackInput): FeedbackItem {
  if (!i.handDetected) {
    const part = i.partLabel ?? "open hand";
    return {
      level: "error",
      message:
        part === "open hand"
          ? "Bring your open hand in front of the camera"
          : `Step back so your full ${part} is visible to the camera`,
    };
  }
  if (i.trackerFeedback.some((f) => f.startsWith("Slow down"))) {
    return { level: "warn", message: "Slow down your movement" };
  }
  if (i.trackerFeedback.some((f) => /Range|gehraai/i.test(f))) {
    return { level: "warn", message: "Try a fuller range — move slowly and smoothly" };
  }
  if (i.steadyWristRequired && i.wristUnstable) {
    return { level: "error", message: "Keep your wrist straight and steady" };
  }
  const p = phrasesFor(i.movementType);
  if (i.rangeScore >= 0.72) return { level: "good", message: p.good };
  if (i.phase === "a" && i.rangeScore < 0.5) return { level: "warn", message: p.deeper };
  return { level: "warn", message: i.targetLabel || p.good };
}

// ---------------------------------------------------------------------------
// Session statistics → results card
// ---------------------------------------------------------------------------

/** Typical anatomical ROM windows used to translate depth scores into degrees. */
const ROM_RANGE: Record<string, [number, number]> = {
  flexion: [15, 95],
  extension: [10, 70],
  combined_flexion: [15, 100],
  combined: [10, 110],
  isometric_grip: [10, 80],
  abduction: [10, 35],
  thumb_abduction: [15, 55],
  opposition: [20, 70],
  rotation: [30, 90],
  rotation_strength: [20, 80],
  deviation: [10, 40],
  elbow_flexion: [20, 145],
  // ---- pose-tracked movements (screen-plane estimates) ----
  elbow_rom: [45, 145],
  shoulder_elev: [40, 165],
  light_raise: [30, 90],
  front_raise: [40, 100],
  side_raise: [35, 90],
  wall_slides: [45, 150],
  shoulder_abduct: [35, 150],
  shoulder_extension: [10, 40],
  shoulder_crossbody: [20, 55],
  shoulder_behind: [15, 45],
  forearm_er: [25, 60],
  wrist_rom: [15, 65],
};

export interface ResultCheck {
  ok: boolean;
  text: string;
}

export interface SessionResultSummary {
  reps: number;
  plannedReps: number;
  formScore: number;
  qualityLabel: "Good" | "Fair" | "Needs work";
  romDeg: number | null;
  incorrectReps: number;
  checklist: ResultCheck[];
}

export function qualityLabelFor(formPct: number): SessionResultSummary["qualityLabel"] {
  if (formPct >= 85) return "Good";
  if (formPct >= 65) return "Fair";
  return "Needs work";
}

export class SessionStats {
  totalFrames = 0;
  activeFrames = 0;
  noHandFrames = 0;
  unstableFrames = 0;

  private qualitySum = 0;
  private emaRange = 0.5;
  private repsSeen = 0;
  private fastReps = 0;
  private partialReps = 0;

  frame(handDetected: boolean): void {
    this.totalFrames += 1;
    if (handDetected) this.activeFrames += 1;
    else this.noHandFrames += 1;
  }

  observe(rangeScore: number, wristUnstable: boolean): void {
    const r = Math.max(0, Math.min(1, rangeScore));
    this.qualitySum += r;
    this.emaRange += (r - this.emaRange) * 0.08;
    if (wristUnstable) this.unstableFrames += 1;
  }

  onTracker(st: TrackerState): void {
    if (st.reps > this.repsSeen) {
      const gained = st.reps - this.repsSeen;
      this.repsSeen = st.reps;
      // shallow recent depth ⇒ those reps did not reach full range
      if (this.emaRange < 0.55) this.partialReps += Math.min(gained, 2);
    }
    if (st.feedback.some((f) => f.startsWith("Slow down"))) this.fastReps += 1;
  }

  formPct(): number {
    if (this.activeFrames === 0) return 100;
    const depth = this.qualitySum / this.activeFrames;
    const presence = this.activeFrames / Math.max(this.totalFrames, 1);
    let score = 55 + depth * 40; // movement depth dominates the score
    score *= 0.7 + 0.3 * presence; // penalise hand dropouts
    score -= Math.min(20, this.fastReps * 3 + this.partialReps * 2);
    return Math.max(0, Math.min(100, Math.round(score)));
  }

  incorrectReps(): number {
    return Math.min(this.repsSeen, this.partialReps + Math.min(this.fastReps, 2));
  }

  romEstimate(movementType: string): number | null {
    const range = ROM_RANGE[movementType];
    if (!range || this.activeFrames < 10) return null;
    const [lo, hi] = range;
    return Math.round(lo + this.emaRange * (hi - lo));
  }

  summary(movementType: string, plannedReps: number, partLabel = "Hand"): SessionResultSummary {
    const formScore = this.formPct();
    const checklist: ResultCheck[] = [];
    checklist.push({ ok: true, text: `${this.repsSeen} repetitions tracked by AI` });
    checklist.push(
      this.fastReps === 0
        ? { ok: true, text: "Controlled speed throughout" }
        : { ok: false, text: `${this.fastReps} rep${this.fastReps > 1 ? "s" : ""} moved too fast` },
    );
    const unstableRatio = this.activeFrames ? this.unstableFrames / this.activeFrames : 0;
    checklist.push(
      unstableRatio <= 0.15
        ? { ok: true, text: needsSteadyWrist(movementType) ? "Wrist stayed straight and steady" : "Steady, controlled position" }
        : { ok: false, text: `Keep your ${partLabel.toLowerCase()} stable next time` },
    );
    if (this.partialReps > 0) {
      checklist.push({ ok: false, text: `${this.partialReps} rep${this.partialReps > 1 ? "s" : ""} missed full range` });
    }
    const dropoutRatio = this.totalFrames ? this.noHandFrames / this.totalFrames : 0;
    if (dropoutRatio > 0.25) {
      checklist.push({ ok: false, text: `${partLabel} left the camera view frequently` });
    }
    const romDeg = this.romEstimate(movementType);
    if (romDeg !== null) {
      checklist.push({ ok: true, text: `Estimated range of motion ≈ ${romDeg}°` });
    }
    return {
      reps: this.repsSeen,
      plannedReps,
      formScore,
      qualityLabel: qualityLabelFor(formScore),
      romDeg,
      incorrectReps: this.incorrectReps(),
      checklist,
    };
  }
}
