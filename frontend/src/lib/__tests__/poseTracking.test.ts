import { describe, expect, it } from "vitest";
import { computePoseMetrics, makePoseTracker, type PoseFrameMetrics, type PoseLandmark } from "@/lib/poseTracking";
import type { RepTracker } from "@/lib/handTracking";

/** Minimal BlazePose layout: torso fixed, left arm posed by the caller. */
function basePose(): PoseLandmark[] {
  const lm: PoseLandmark[] = Array.from({ length: 33 }, () => ({ x: 0.5, y: 0.5, z: 0 }));
  lm[11] = { x: 0.45, y: 0.3, z: 0 }; // L shoulder
  lm[12] = { x: 0.55, y: 0.3, z: 0 }; // R shoulder
  lm[13] = { x: 0.45, y: 0.5, z: 0 }; // L elbow — hanging by default
  lm[14] = { x: 0.55, y: 0.5, z: 0 }; // R elbow
  lm[15] = { x: 0.45, y: 0.62, z: 0 }; // L wrist
  lm[16] = { x: 0.55, y: 0.62, z: 0 }; // R wrist
  lm[23] = { x: 0.45, y: 0.6, z: 0 }; // L hip
  lm[24] = { x: 0.55, y: 0.6, z: 0 }; // R hip
  return lm;
}

describe("computePoseMetrics elevation scale", () => {
  it("maps a hanging arm to ~0°", () => {
    const m = computePoseMetrics(basePose())!;
    expect(Math.round(m.elevationDeg)).toBe(0);
  });

  it("maps a horizontal arm to ~90°", () => {
    const lm = basePose();
    lm[13] = { x: 0.25, y: 0.3, z: 0 };
    lm[15] = { x: 0.1, y: 0.3, z: 0 };
    expect(Math.round(computePoseMetrics(lm)!.elevationDeg)).toBe(90);
  });

  it("maps an overhead arm near 180°", () => {
    const lm = basePose();
    lm[13] = { x: 0.45, y: 0.12, z: 0 };
    lm[15] = { x: 0.45, y: 0.02, z: 0 };
    expect(computePoseMetrics(lm)!.elevationDeg).toBeGreaterThan(160);
  });
});

describe("pose rep sessions complete", () => {
  it("shoulder_elev counts a raise-lower cycle (thresholds reachable)", () => {
    const tracker = makePoseTracker("shoulder_elev") as RepTracker<PoseFrameMetrics>;
    let t = 0;
    const run = (elbowY: number, wristY: number, n: number) => {
      let st = { reps: 0 };
      for (let i = 0; i < n; i++) {
        const lm = basePose();
        lm[13] = { x: 0.45, y: elbowY, z: 0 };
        lm[15] = { x: 0.45, y: wristY, z: 0 };
        t += 40;
        st = tracker.update(computePoseMetrics(lm)!, t);
      }
      return st.reps;
    };
    run(0.5, 0.62, 8); // hanging — neutral
    expect(run(0.12, 0.02, 8)).toBe(0); // raise overhead — arms the rep
    expect(run(0.5, 0.62, 8)).toBe(1); // lower — rep completes
  });

  it("elbow_rom counts even when the session starts with the elbow bent", () => {
    const tracker = makePoseTracker("elbow_rom") as RepTracker<PoseFrameMetrics>;
    let t = 0;
    const run = (wrist: { x: number; y: number }, n: number) => {
      let st = { reps: 0 };
      for (let i = 0; i < n; i++) {
        const lm = basePose();
        lm[13] = { x: 0.45, y: 0.42, z: 0 }; // bent elbow
        lm[15] = { x: wrist.x, y: wrist.y, z: 0 };
        t += 40;
        st = tracker.update(computePoseMetrics(lm)!, t);
      }
      return st.reps;
    };
    // starts already in the extreme zone (<85°) — must still arm and count
    expect(run({ x: 0.47, y: 0.34 }, 10)).toBe(0);
    expect(run({ x: 0.45, y: 0.62 }, 6)).toBe(1); // straighten fully
  });
});
