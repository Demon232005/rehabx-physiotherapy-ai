import { describe, expect, it } from "vitest";
import {
  RepTracker,
  computeMetrics,
  painAdjustedTargets,
  type Landmark,
} from "@/lib/handTracking";

/** Synthetic hand: wrist at origin-ish, palm size 0.1, all fingertips at `tipDist` below the wrist. */
function syntheticHand(tipDist: number): Landmark[] {
  const lm: Landmark[] = [];
  const push = (x: number, y: number) => lm.push({ x, y, z: 0 });
  push(0.5, 0.6); // 0 wrist
  // thumb chain: joints at indices 1-4 (4 = thumb tip; unused by openness)
  for (let i = 0; i < 4; i++) push(0.4 + i * 0.01, 0.5);
  // palm reference: middle MCP at distance 0.1 above wrist
  push(0.5, 0.5); // 5
  push(0.5, 0.49);
  push(0.5, 0.48);
  push(0.5, 0.47); // 8 index tip
  push(0.52, 0.5); // 9 middle MCP -> palm size = 0.1
  push(0.52, 0.49);
  push(0.52, 0.48);
  push(0.52, 0.6 - tipDist); // 12
  push(0.54, 0.5); // 13
  push(0.54, 0.49);
  push(0.54, 0.48);
  push(0.54, 0.6 - tipDist); // 16
  push(0.56, 0.5); // 17
  push(0.56, 0.49);
  push(0.56, 0.48);
  push(0.56, 0.6 - tipDist); // 20 pinky tip
  return lm;
}

describe("computeMetrics", () => {
  it("returns higher openness for an extended hand than a curled one", () => {
    const open = computeMetrics(syntheticHand(0.19))!;
    const closed = computeMetrics(syntheticHand(0.08))!;
    expect(open.openness).toBeGreaterThan(closed.openness);
    expect(open.openness).toBeGreaterThan(1.5);
    expect(closed.openness).toBeLessThan(1.05);
  });

  it("returns null for incomplete landmarks", () => {
    expect(computeMetrics([])).toBeNull();
    expect(computeMetrics(syntheticHand(0.1).slice(0, 10))).toBeNull();
  });
});

describe("RepTracker", () => {
  it("counts one rep per full close-open cycle", () => {
    const tracker = new RepTracker("flexion");
    let reps = 0;
    let t = 0;
    const frame = (tipDist: number) => {
      const m = computeMetrics(syntheticHand(tipDist))!;
      t += 40;
      reps = tracker.update(m, t).reps;
    };
    // hold open, then closed, then open again = 1 rep
    for (let i = 0; i < 6; i++) frame(0.19);
    for (let i = 0; i < 6; i++) frame(0.08);
    expect(reps).toBe(0);
    for (let i = 0; i < 6; i++) frame(0.19);
    expect(reps).toBe(1);
    // second cycle
    for (let i = 0; i < 6; i++) frame(0.08);
    for (let i = 0; i < 6; i++) frame(0.19);
    expect(reps).toBe(2);
  });

  it("does not count jitter around one threshold", () => {
    const tracker = new RepTracker("flexion");
    let reps = 0;
    let t = 0;
    for (let k = 0; k < 20; k++) {
      const d = k % 2 === 0 ? 1.3 : 1.36; // hovers between thresholds
      const m = computeMetrics(syntheticHand(d === 1.3 ? 0.13 : 0.14))!;
      t += 40;
      reps = tracker.update(m, t).reps;
    }
    expect(reps).toBe(0);
  });

  it("flags too-fast reps in feedback", () => {
    const tracker = new RepTracker("flexion");
    let sawSlowDown = false;
    let t = 0;
    const frame = (tipDist: number) => {
      const m = computeMetrics(syntheticHand(tipDist))!;
      t += 10; // 10 ms per phase -> way under the 350 ms minimum
      // feedback is transient (the UI shows whatever the latest frame reports)
      if (tracker.update(m, t).feedback.some((f) => f.includes("Slow down"))) {
        sawSlowDown = true;
      }
    };
    for (let i = 0; i < 6; i++) frame(0.19);
    for (let i = 0; i < 6; i++) frame(0.08);
    for (let i = 0; i < 6; i++) frame(0.19);
    expect(sawSlowDown).toBe(true);
  });
});

describe("painAdjustedTargets", () => {
  it("halves dosage at severe pain", () => {
    const t = painAdjustedTargets(8, 20, 3);
    expect(t.reps).toBe(10);
    expect(t.sets).toBe(1);
    expect(t.intensity).toBe("minimal");
    expect(t.warning).toContain("Stop");
  });

  it("uses three-quarter dosage at moderate pain", () => {
    const t = painAdjustedTargets(4, 20, 3);
    expect(t.reps).toBe(15);
    expect(t.sets).toBe(2);
    expect(t.intensity).toBe("low");
  });

  it("keeps full range when pain is low", () => {
    const t = painAdjustedTargets(1, 20, 3);
    expect(t.reps).toBe(20);
    expect(t.sets).toBe(3);
    expect(t.intensity).toBe("normal");
  });
});
