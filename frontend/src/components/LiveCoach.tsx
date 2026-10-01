"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { ExerciseOut } from "@/lib/types";
import {
  RepTracker,
  computeMetrics,
  painAdjustedTargets,
  type Landmark,
  type TrackerLike,
  type TrackerState,
} from "@/lib/handTracking";
import {
  ScapMonitor,
  HoldTracker,
  computePoseMetrics,
  makePoseTracker,
  type PoseLandmark,
} from "@/lib/poseTracking";
import {
  LEVEL_DOT,
  SessionStats,
  WristMonitor,
  buildLiveFeedback,
  needsSteadyWrist,
  qualityLabelFor,
  type FeedbackItem,
  type SessionResultSummary,
} from "@/lib/handFeedback";
import { difficultyLabel, getExerciseMetaForRow, resolveTrackingMode, type TrackingMode } from "@/lib/exerciseLibrary";
import type { FrameMetrics } from "@/lib/handTracking";
import type { PoseFrameMetrics } from "@/lib/poseTracking";
import ExerciseTutorial from "@/components/ExerciseTutorial";

type FrameMetricsLike = FrameMetrics | PoseFrameMetrics;

// Self-hosted: no CDN dependency — works offline and on restricted networks
const WASM_BASE = "/mediapipe";
const MODEL_URL = "/models/hand_landmarker.task";
const POSE_MODEL_URL = "/models/pose_landmarker_lite.task";

type DetectionResult = { landmarks: Landmark[][] };
type LandmarkerLike = {
  detectForVideo: (v: HTMLVideoElement, t: number) => DetectionResult;
  close?: () => void;
};

function withTimeout<T>(p: Promise<T>, ms: number, msg: string): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const t = setTimeout(() => reject(new Error(msg)), ms);
    p.then(
      (v) => {
        clearTimeout(t);
        resolve(v);
      },
      (e) => {
        clearTimeout(t);
        reject(e);
      }
    );
  });
}

/**
 * Singleton loaders — one per tracking mode, created once, reused across
 * sessions. CPU delegate only: it initialises in ~1-2s and never hangs,
 * unlike GPU shader compilation on some Windows drivers. Warmed up while
 * the user is still on the pain screen. ONE camera stream feeds whichever
 * landmarker(s) the exercise requires — never multiple getUserMedia calls.
 */
let handLandmarkerPromise: Promise<LandmarkerLike> | null = null;
let poseLandmarkerPromise: Promise<LandmarkerLike> | null = null;

function getHandLandmarker(): Promise<LandmarkerLike> {
  if (!handLandmarkerPromise) {
    handLandmarkerPromise = withTimeout(
      (async () => {
        installMediaPipeLogFilter();
        const vision = await import("@mediapipe/tasks-vision");
        const fileset = await vision.FilesetResolver.forVisionTasks(WASM_BASE);
        return vision.HandLandmarker.createFromOptions(fileset, {
          baseOptions: { modelAssetPath: MODEL_URL, delegate: "CPU" },
          runningMode: "VIDEO",
          numHands: 1,
        }) as unknown as LandmarkerLike;
      })(),
      30000,
      "Model load timed out — page refresh karke dobara try karo"
    ).catch((e) => {
      handLandmarkerPromise = null; // allow a fresh attempt next time
      throw e;
    });
  }
  return handLandmarkerPromise;
}

function getPoseLandmarker(): Promise<LandmarkerLike> {
  if (!poseLandmarkerPromise) {
    poseLandmarkerPromise = withTimeout(
      (async () => {
        installMediaPipeLogFilter();
        const vision = await import("@mediapipe/tasks-vision");
        const fileset = await vision.FilesetResolver.forVisionTasks(WASM_BASE);
        return vision.PoseLandmarker.createFromOptions(fileset, {
          baseOptions: { modelAssetPath: POSE_MODEL_URL, delegate: "CPU" },
          runningMode: "VIDEO",
          numPoses: 1,
        }) as unknown as LandmarkerLike;
      })(),
      30000,
      "Model load timed out — page refresh karke dobara try karo"
    ).catch((e) => {
      poseLandmarkerPromise = null; // allow a fresh attempt next time
      throw e;
    });
  }
  return poseLandmarkerPromise;
}

function getLandmarker(mode: TrackingMode): Promise<LandmarkerLike> {
  // hand+pose needs BOTH models — warm them in parallel on the same frames
  if (mode === "pose") return getPoseLandmarker();
  return getHandLandmarker();
}

const HAND_CONNECTIONS: [number, number][] = [
  [0, 1], [1, 2], [2, 3], [3, 4],
  [0, 5], [5, 6], [6, 7], [7, 8],
  [5, 9], [9, 10], [10, 11], [11, 12],
  [9, 13], [13, 14], [14, 15], [15, 16],
  [13, 17], [17, 18], [18, 19], [19, 20],
  [0, 17],
];

/** Arm + torso subset of BlazePose — enough to coach upper-limb exercises. */
const POSE_CONNECTIONS: [number, number][] = [
  [11, 12], // shoulders
  [11, 13], [13, 15], // left arm
  [12, 14], [14, 16], // right arm
  [11, 23], [12, 24], // torso sides
  [23, 24], // hips
];

const POSE_KEYPOINTS = [11, 12, 13, 14, 15, 16, 23, 24];

/** One shared factory: the exercise's tracking mode picks the right engine. */
function makeTracker(movementType: string, mode: TrackingMode): TrackerLike | HoldTracker {
  if (mode === "hand") return new RepTracker(movementType);
  return makePoseTracker(movementType);
}

/**
 * Session phases:
 *  pain    — dosage slider (pain-adjusted targets)
 *  loading — camera + model initialisation
 *  ready   — live camera & hand landmarks on, tutorial visible, NOT counting
 *  run     — "Start Exercise" pressed: rep counting + AI feedback active
 *  done    — hand-specific results card
 *  error   — camera/model failure with diagnostics
 */
type Step = "pain" | "loading" | "ready" | "run" | "done" | "error";

function sleep(ms: number) {
  return new Promise((r) => setTimeout(r, ms));
}

/**
 * MediaPipe's WASM glue forwards TFLite/native stderr to console.error/warn
 * asynchronously (after detectForVideo returns), so per-call muting can't
 * catch it. Install a one-time filter that drops only the known-benign native
 * log lines — real errors and warnings still surface normally.
 */
let logFilterInstalled = false;

function installMediaPipeLogFilter() {
  if (logFilterInstalled || typeof window === "undefined") return;
  logFilterInstalled = true;
  const benign = [
    /^INFO: .*(TensorFlow|XNNPACK|delegate)/i,
    /OpenGL error checking is disabled/,
    /Feedback manager requires a model with a single signature inference/,
    /NORM_RECT without IMAGE_DIMENSIONS is only supported for the square ROI/,
  ];
  const isBenign = (args: unknown[]) => {
    const first = args[0];
    return typeof first === "string" && benign.some((re) => re.test(first));
  };
  for (const method of ["error", "warn"] as const) {
    const original = console[method].bind(console);
    console[method] = (...args: unknown[]) => {
      if (!isBenign(args)) original(...args);
    };
  }
}

/** Device that worked before — future sessions open it directly. */
let lastGoodDeviceId = "";

/**
 * Dev-only diagnostics. Next.js inlines NODE_ENV, so the whole branch is
 * compiled out of production builds — no logs leak to real users.
 */
function dbg(...args: unknown[]) {
  if (process.env.NODE_ENV !== "production") console.log("[rehabx-camera]", ...args);
}

function errName(e: unknown): string {
  return e instanceof DOMException ? e.name : e instanceof Error ? e.name : "";
}

/** One clear, actionable message per getUserMedia failure type. */
function cameraErrorMessage(e: unknown): string {
  switch (errName(e)) {
    case "NotAllowedError":
    case "PermissionDeniedError":
      return "Camera permission blocked hai. Browser address bar me lock icon → Site settings → Camera = Allow karo, phir 'Retry' dabao.";
    case "NotFoundError":
    case "DevicesNotFoundError":
      return "Koi camera detect nahi hua — check ki webcam connected aur enabled hai.";
    case "NotReadableError":
    case "TrackStartError":
      // Diagnostics showed this occurs even for a bare getUserMedia on a
      // machine with a single camera — i.e. OS/driver level refusal, not an
      // in-app lifecycle problem. Give the fix ladder, not vague blame.
      return "OS/driver ne camera start karne se mana kar diya (RehabX ka lifecycle clean hai). Try karo: 1) Fn+F8 / privacy shutter ON to nahi, 2) Zoom/Teams/baki browser windows band karo, 3) Lenovo Vantage → Camera Privacy Mode OFF, 4) Device Manager → Cameras → Integrated Camera → Disable phir Enable.";
    case "OverconstrainedError":
      return "Selected camera abhi available nahi hai. 'Default camera' select karke try karo.";
    case "AbortError":
      return "Camera start karte waqt device ne respond karna band kar diya. Ek baar 'Retry' dabao.";
    case "SecurityError":
      return "Browser ne camera access block kiya (insecure context). localhost ya HTTPS par kholo.";
    case "InsecureContextError":
      return "Camera sirf secure context me chalta hai — page ko HTTPS ya http://localhost par kholo.";
    case "CameraUnsupportedError":
      return "Is browser/context me Camera API uplabdh nahi hai — koi modern browser (Chrome/Edge) use karo.";
    default:
      return e instanceof Error ? `Could not start live tracking: ${e.message}` : "Could not start live tracking.";
  }
}

async function listVideoInputs(): Promise<MediaDeviceInfo[]> {
  try {
    const devices = await navigator.mediaDevices.enumerateDevices();
    return devices.filter((d) => d.kind === "videoinput");
  } catch {
    return [];
  }
}

/**
 * True when a <video> element on THIS page still holds a live camera track —
 * i.e., RehabX itself is holding the device. Used to avoid falsely telling
 * the user "another app is busy" when the fault would be ours.
 */
function rehabHoldsCamera(): boolean {
  if (typeof document === "undefined") return false;
  return Array.from(document.querySelectorAll("video")).some((v) => {
    const s = v.srcObject as MediaStream | null;
    return !!s && s.getVideoTracks().some((t) => t.readyState === "live");
  });
}

/** Thrown before any getUserMedia when the environment can't do camera at all. */
function preconditionError(name: string, message: string): Error {
  return Object.assign(new Error(message), { name });
}

/**
 * STEP preflight: never attempt camera access outside a secure context or
 * without the mediaDevices API. Both produce distinct, honest errors instead
 * of confusing downstream NotReadable-style failures.
 */
function assertCameraSupport(): void {
  if (typeof window !== "undefined" && !window.isSecureContext) {
    throw preconditionError(
      "InsecureContextError",
      "Camera needs HTTPS ya localhost. Current page insecure context me chal rahi hai.",
    );
  }
  if (!navigator.mediaDevices || typeof navigator.mediaDevices.getUserMedia !== "function") {
    throw preconditionError(
      "CameraUnsupportedError",
      "Is browser/context me Camera API (mediaDevices.getUserMedia) available nahi hai.",
    );
  }
}

async function cameraPermissionState(): Promise<string | undefined> {
  try {
    const p = await navigator.permissions.query({ name: "camera" as PermissionName });
    return p.state;
  } catch {
    return undefined; // Firefox/Safari may not support the camera permission name
  }
}

/**
 * Isolation test: bare getUserMedia with zero MediaPipe involvement.
 * PASS → hardware/browser fine, RehabX lifecycle at fault.
 * FAIL → browser/permission/device/OS issue.
 */
async function minimalCameraTest(): Promise<string> {
  try {
    const s = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
    const t = s.getVideoTracks()[0];
    const detail = `${t?.label || "(unknown device)"}, readyState=${t?.readyState}`;
    s.getTracks().forEach((tr) => tr.stop());
    return `PASS (${detail})`;
  } catch (e) {
    return `FAIL ${errName(e)}: ${e instanceof Error ? e.message : String(e)}`;
  }
}

/** Full diagnostic snapshot for the error panel / dev console. */
async function collectCameraDiagnostics(err: unknown): Promise<Record<string, unknown>> {
  const constraint = (err as { constraint?: unknown })?.constraint;
  return {
    "Actual error": `${errName(err)}: ${err instanceof Error ? err.message : String(err)}`,
    Constraint: constraint !== undefined ? JSON.stringify(constraint) : "(n/a)",
    "Secure context": typeof window !== "undefined" ? window.isSecureContext : false,
    "Camera API supported": typeof navigator !== "undefined" && !!navigator.mediaDevices?.getUserMedia,
    "Permission state": await cameraPermissionState().then((s) => s ?? "(not supported)"),
    "Available cameras": (await listVideoInputs()).map((d) => d.label || "(label hidden until grant)"),
    "RehabX holds live stream": rehabHoldsCamera(),
    "Last known-good device": lastGoodDeviceId || "(none)",
    "Isolation test (bare getUserMedia, no MediaPipe)": await minimalCameraTest(),
  };
}

// Dev-console access for debugging without triggering the UI flow.
declare global {
  interface Window {
    __rehabxCamera?: {
      diagnose: () => Promise<Record<string, unknown>>;
      minimalTest: () => Promise<string>;
    };
  }
}
if (process.env.NODE_ENV !== "production" && typeof window !== "undefined") {
  window.__rehabxCamera ??= {
    diagnose: () => collectCameraDiagnostics(null),
    minimalTest: minimalCameraTest,
  };
}

function constraintsFor(id?: string): MediaStreamConstraints {
  return id
    ? { video: { deviceId: { ideal: id }, width: { ideal: 640 }, height: { ideal: 480 } }, audio: false }
    : { video: true, audio: false };
}

/**
 * Open the camera in AT MOST TWO getUserMedia attempts — no device storms:
 *
 * Attempt 1: validated user-selected device (`ideal`), else plain default
 *   {video:true}. Never loops through cameras.
 * On transient failure: full self-release via opts.release(), 500ms settle,
 *   fresh enumeration — then:
 * Attempt 2: plain {video:true} default.
 * Still failing → throw the ORIGINAL error; caller surfaces real diagnostics.
 *
 * Fatal errors (NotAllowed/Security) throw immediately. Every success is
 * verified to contain a LIVE video track before being trusted.
 */
async function acquireStream(
  preferredDeviceId: string | undefined,
  opts: { recentReleaseMs: number; release: () => void },
): Promise<MediaStream> {
  const fatal = (name: string) =>
    name === "NotAllowedError" ||
    name === "PermissionDeniedError" ||
    name === "SecurityError";

  dbg("CAMERA INIT START", { preferred: preferredDeviceId || "(browser default)", lastGood: lastGoodDeviceId || "(none)", recentReleaseMs: opts.recentReleaseMs });
  const inputs = await listVideoInputs();
  dbg("available video devices", inputs.map((d) => ({ label: d.label || "(hidden)", id: d.deviceId.slice(0, 8) })));

  // never constrain on a stale/nonexistent device id
  let preferred = preferredDeviceId;
  if (preferred && !inputs.some((d) => d.deviceId === preferred)) {
    dbg("selected device no longer present — using browser default");
    preferred = undefined;
  }

  let lastErr: unknown;
  /** One getUserMedia attempt; verifies the returned track is actually live. */
  const attempt = async (constraints: MediaStreamConstraints, tag: string): Promise<MediaStream | null> => {
    try {
      dbg("GET USER MEDIA START", tag, JSON.stringify(constraints.video));
      const stream = await navigator.mediaDevices.getUserMedia(constraints);
      const tracks = stream.getVideoTracks();
      dbg(
        "STREAM TRACKS",
        tracks.map((t) => ({ id: t.id, label: t.label, readyState: t.readyState, enabled: t.enabled, muted: t.muted })),
      );
      if (!tracks.length || tracks.some((t) => t.readyState !== "live")) {
        throw new Error("getUserMedia returned a non-live video track");
      }
      dbg("GET USER MEDIA SUCCESS", tracks.map((t) => `${t.label || "track"}(${t.id})`).join(", "));
      const opened = tracks[0]?.getSettings().deviceId;
      if (opened) lastGoodDeviceId = opened;
      return stream;
    } catch (e) {
      lastErr = e;
      // expose the REAL error — name, message and over-constrained target
      dbg("CAMERA ERROR", errName(e), e instanceof Error ? e.message : "", (e as { constraint?: unknown })?.constraint ?? "");
      if (fatal(errName(e))) throw e;
      return null;
    }
  };

  // ---- Attempt 1 ----
  const first = await attempt(constraintsFor(preferred), "attempt 1");
  if (first) return first;

  // ---- Between attempts: full self-release, settle, re-enumerate ----
  opts.release();
  await sleep(500);

  // ---- Attempt 2: plain browser default ----
  const second = await attempt({ video: true, audio: false }, "attempt 2 (default)");
  if (second) return second;

  throw lastErr ?? new Error("camera unavailable");
}

/** The <video> only mounts on the loading/run screens — wait for React to flush it. */
async function waitForVideoElement(get: () => HTMLVideoElement | null): Promise<HTMLVideoElement> {
  for (let i = 0; i < 100; i++) {
    const v = get();
    if (v) return v;
    await sleep(50);
  }
  throw new Error("Video element did not become ready");
}

/**
 * Attach the stream and resolve only when frames are really flowing:
 * readyState >= HAVE_CURRENT_DATA (loadeddata) AND video.play() succeeded.
 * MediaPipe detection starts strictly after this resolves.
 */
function attachAndPlay(video: HTMLVideoElement, stream: MediaStream): Promise<void> {
  return new Promise<void>((resolve, reject) => {
    dbg("attaching stream to <video>");
    video.srcObject = stream;
    let settled = false;
    const finish = (fn: () => void) => {
      if (settled) return;
      settled = true;
      video.removeEventListener("loadeddata", onReady);
      video.removeEventListener("error", onError);
      fn();
    };
    const onReady = () => {
      dbg("VIDEO METADATA READY", { readyState: video.readyState, size: `${video.videoWidth}x${video.videoHeight}` });
      video
        .play()
        .then(() => {
          dbg("VIDEO PLAY SUCCESS", { paused: video.paused, readyState: video.readyState });
          finish(resolve);
        })
        .catch((e) => {
          dbg("VIDEO PLAY CANCELLED", errName(e), e instanceof Error ? e.message : "");
          finish(() => reject(e));
        });
    };
    const onError = () => finish(() => reject(new Error("Video element failed to read the camera stream")));
    if (video.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA) onReady();
    else {
      video.addEventListener("loadeddata", onReady);
      video.addEventListener("error", onError);
    }
  });
}

export default function LiveCoach({
  exercise,
  onClose,
  analysisId,
}: {
  exercise: ExerciseOut;
  onClose: () => void;
  /** Analysis behind a report-backed recommendation card; links the session
   * and its auto-logged progress to that injury (spec §18-§19). */
  analysisId?: string;
}) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const rafRef = useRef<number>(0);
  const trackerRef = useRef<TrackerLike | HoldTracker | null>(null);
  const landmarkerRef = useRef<LandmarkerLike | null>(null);
  const fusionRef = useRef<LandmarkerLike | null>(null); // hand model for hand+pose fusion
  const lastVideoTimeRef = useRef(-1);
  const noHandFramesRef = useRef(0);
  const startingRef = useRef(false); // single-flight lock — no concurrent getUserMedia
  const runIdRef = useRef(0); // bumped to cancel any in-flight camera work
  const lastReleaseAtRef = useRef(0); // when our tracks were last stopped
  const runningRef = useRef(false); // true once "Start Exercise" begins rep counting
  const finishedRef = useRef(false); // auto-finish latch (target reached)
  const startedAtRef = useRef<number | null>(null); // wall clock at "Start Exercise"
  const progressLoggedRef = useRef(false); // one progress entry per session, ever
  const statsRef = useRef(new SessionStats());
  const wristRef = useRef(new WristMonitor());
  const scapRef = useRef(new ScapMonitor());

  const [step, setStep] = useState<Step>("pain");
  const [errorMsg, setErrorMsg] = useState("");
  const [painLevel, setPainLevel] = useState(2);
  const [trackerState, setTrackerState] = useState<TrackerState | null>(null);
  const targets = painAdjustedTargets(painLevel, exercise.rep_range_max, exercise.set_range_max);
  const [saved, setSaved] = useState<"pending" | "saved" | "error">("pending");
  const [logState, setLogState] = useState<"pending" | "saved" | "error" | "skipped">("pending");
  const [cameras, setCameras] = useState<{ value: string; label: string }[]>([]);
  const [deviceId, setDeviceId] = useState("");
  const [handDetected, setHandDetected] = useState(false);
  const [feedbackItem, setFeedbackItem] = useState<FeedbackItem | null>(null);
  const [result, setResult] = useState<SessionResultSummary | null>(null);

  // Which AI models does THIS exercise need? One stream, right-sized pipeline.
  const trackingMode: TrackingMode = resolveTrackingMode(exercise);
  const poseBased = trackingMode !== "hand";
  const needsFusion = trackingMode === "hand+pose";
  const partLabel = poseBased ? (trackingMode === "pose" ? "upper body" : "arm and hand") : "open hand";

  // exercise metadata (tutorial, steps, joints…) — derived from the row itself
  const meta = getExerciseMetaForRow(exercise);
  const instructions =
    meta.instructions.length > 0
      ? meta.instructions
      : [exercise.starting_position, exercise.required_movement].filter(Boolean);
  const safetyTips = [...new Set([...meta.safetyTips, ...exercise.contraindications])].slice(0, 3);

  const refreshCameras = useCallback(() => {
    navigator.mediaDevices
      ?.enumerateDevices()
      .then((ds) => {
        const cams = ds.filter((d) => d.kind === "videoinput");
        setCameras(cams.map((c, i) => ({ value: c.deviceId, label: c.label || `Camera ${i + 1}` })));
      })
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    refreshCameras();
  }, [refreshCameras]);

  // session row is created only when the user commits to exercising
  const sessionRef = useRef<string | null>(null);
  const [camDiag, setCamDiag] = useState<Record<string, unknown> | null>(null);

  /** Release everything WE hold — without invalidating an in-flight flow. */
  const releaseStream = useCallback(() => {
    cancelAnimationFrame(rafRef.current);
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => {
        dbg("Stopping old camera track:", t.id, t.readyState);
        t.stop();
      });
      dbg("CAMERA TRACK STOPPED");
      streamRef.current = null;
    }
    // drop the reference to the dead stream so the device can be re-opened
    const v = videoRef.current;
    if (v) {
      try {
        v.pause();
      } catch {
        /* already stopped */
      }
      if (v.srcObject) {
        v.srcObject = null; // stale srcObject keeps tracks referenced → delays hardware release
        dbg("stale srcObject cleared");
      }
    }
    lastReleaseAtRef.current = Date.now();
  }, []);

  const stopCamera = useCallback(() => {
    runIdRef.current += 1; // any in-flight acquisition is now stale
    releaseStream();
  }, [releaseStream]);

  useEffect(() => {
    // warm up ONLY the model(s) this exercise needs while the user is still
    // on the pain screen — no unnecessary models ever initialise
    getLandmarker(trackingMode).catch(() => undefined);
    return () => {
      runIdRef.current += 1; // invalidate anything in flight (StrictMode-safe)
      stopCamera();
      dbg("CAMERA CLEANUP — component unmounted, camera released");
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function startSession() {
    // one flow at a time — a second click/Retry can never race the first
    if (startingRef.current) {
      dbg("CAMERA INIT SKIPPED - ALREADY INITIALIZING");
      return;
    }
    startingRef.current = true;
    setStep("loading");
    setErrorMsg("");
    setCamDiag(null);
    try {
      // preflight: secure context + API support — honest failure before any
      // getUserMedia is attempted
      assertCameraSupport();
      dbg("session start requested", { deviceId: deviceId || "(default)" });
      // 1) release whatever held the camera before, then give the OS/driver a
      // moment to finish the asynchronous release. If WE released a stream
      // moments ago, wait a bit longer before asking again.
      stopCamera();
      const runId = ++runIdRef.current; // claim ownership after the invalidation bump
      const stale = () => runIdRef.current !== runId;
      const sinceRelease = lastReleaseAtRef.current ? Date.now() - lastReleaseAtRef.current : Infinity;
      await sleep(sinceRelease < 2000 ? 700 : 300);
      if (stale()) return;

      const stream = await acquireStream(deviceId || undefined, {
        recentReleaseMs: Number.isFinite(sinceRelease) ? sinceRelease : 0,
        release: releaseStream,
      });
      if (stale()) {
        stream.getTracks().forEach((t) => t.stop()); // late resolve — don't leak it
        return;
      }
      streamRef.current = stream;
      refreshCameras(); // labels become available once permission is granted

      // 2) attach and wait until frames are actually flowing
      const video = await waitForVideoElement(() => videoRef.current);
      if (stale()) return;
      await attachAndPlay(video, stream);
      if (stale()) return;

      // 3) tracking model — only after the video element has live frames.
      // hand+pose mode loads both and shares the SAME video element/frames.
      landmarkerRef.current = await getLandmarker(trackingMode);
      if (stale()) return;
      if (needsFusion) {
        fusionRef.current = await getHandLandmarker();
        if (stale()) return;
      } else {
        fusionRef.current = null;
      }
      dbg("MEDIA PIPE READY — starting detection", { mode: trackingMode });

      // 4) hand landmarks are live — enter the "ready" phase WITHOUT counting.
      // The session row is only created when the user presses Start Exercise,
      // so backing out here leaves no orphaned records.
      trackerRef.current = null;
      runningRef.current = false;
      finishedRef.current = false;
      statsRef.current = new SessionStats();
      wristRef.current.reset();
      scapRef.current.reset();
      lastVideoTimeRef.current = -1;
      noHandFramesRef.current = 0;
      setHandDetected(false);
      setFeedbackItem(null);
      setStep("ready");
      loop();
    } catch (e) {
      // NEVER hide the real error — log it with name/message/constraint and
      // capture a full diagnostic snapshot (incl. isolation test).
      dbg("CAMERA ERROR", errName(e), e instanceof Error ? e.message : "");
      stopCamera();
      refreshCameras();
      setErrorMsg(cameraErrorMessage(e));
      setCamDiag(await collectCameraDiagnostics(e).catch(() => null));
      setStep("error");
    } finally {
      startingRef.current = false;
    }
  }

  /** "Start Exercise" — persist the session and begin rep counting + feedback. */
  async function beginExercise() {
    if (step !== "ready" || runningRef.current) return;
    try {
      const s = await api<{ id: string }>("/sessions", {
        method: "POST",
        body: JSON.stringify({
          exercise_id: exercise.id,
          analysis_id: analysisId ?? null,
          planned_reps: targets.reps,
          planned_sets: targets.sets,
        }),
      });
      sessionRef.current = s.id;
    } catch {
      sessionRef.current = null; // track locally even if persistence fails
    }
    trackerRef.current = makeTracker(exercise.movement_type, trackingMode);
    statsRef.current = new SessionStats();
    wristRef.current.reset();
    scapRef.current.reset();
    noHandFramesRef.current = 0;
    finishedRef.current = false;
    startedAtRef.current = Date.now();
    progressLoggedRef.current = false;
    setLogState("pending");
    runningRef.current = true;
    setStep("run");
  }

  function drawOverlay(landmarks: Landmark[] | undefined) {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    if (!landmarks) return;
    // mirrored drawing to match the mirrored video preview
    const px = (x: number) => (1 - x) * canvas.width;
    const connections =
      trackingMode === "hand" ? HAND_CONNECTIONS : POSE_CONNECTIONS;
    ctx.strokeStyle = "#0d9488";
    ctx.lineWidth = 3;
    for (const [a, b] of connections) {
      if (!landmarks[a] || !landmarks[b]) continue;
      ctx.beginPath();
      ctx.moveTo(px(landmarks[a].x), landmarks[a].y * canvas.height);
      ctx.lineTo(px(landmarks[b].x), landmarks[b].y * canvas.height);
      ctx.stroke();
    }
    const dots = trackingMode === "hand" ? landmarks : POSE_KEYPOINTS.map((i) => landmarks[i]).filter(Boolean);
    ctx.fillStyle = "#f59e0b";
    for (const p of dots) {
      ctx.beginPath();
      ctx.arc(px(p.x), p.y * canvas.height, 4, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  /** Unified per-frame pipeline: detect → metrics → tracker → feedback. */
  function loop() {
    rafRef.current = requestAnimationFrame(loop);
    const video = videoRef.current;
    const lm = landmarkerRef.current;
    if (!video || !lm || video.readyState < 2 || !canvasRef.current) return;

    if (video.currentTime === lastVideoTimeRef.current) return;
    lastVideoTimeRef.current = video.currentTime;

    let result: DetectionResult | undefined;
    let fusionResult: DetectionResult | undefined;
    try {
      // rAF callback runs outside render — impure timing is intentional here.
      // The SAME video frame feeds whichever models this exercise requires.
      result = lm.detectForVideo(video, performance.now());
      if (needsFusion && fusionRef.current) {
        fusionResult = fusionRef.current.detectForVideo(video, performance.now());
      }
    } catch {
      return;
    }
    const detectedLandmarks = result.landmarks?.[0];

    if (!poseBased) {
      runHandFrame(detectedLandmarks);
      return;
    }

    const poseLm = detectedLandmarks as PoseLandmark[] | undefined;
    drawOverlay(poseLm as unknown as Landmark[] | undefined);
    const detected = !!poseLm && poseLm.length >= 25;
    setHandDetected(detected);
    statsRef.current.frame(detected);

    if (!detected || !poseLm) {
      noHandFramesRef.current += 1;
      if (runningRef.current && noHandFramesRef.current > 20) {
        setFeedbackItem({
          level: "error",
          message: `Step back so your full ${partLabel} is visible to the camera`,
        });
      } else if (!runningRef.current) {
        setFeedbackItem(null);
      }
      return;
    }
    noHandFramesRef.current = 0;

    const handForFusion = needsFusion ? fusionResult?.landmarks?.[0] ?? null : null;
    const metrics = computePoseMetrics(poseLm, handForFusion);
    if (!metrics) return;

    // scapular-squeeze exercises get their metric from the rolling monitor
    if (exercise.movement_type === "scapular_squeeze") {
      metrics.scapSqueeze = scapRef.current.push(poseLm);
    }

    wristRef.current.push(metrics.elevationDeg); // stability proxy for arm work
    const steadyWristRequired = false; // arm exercises coach posture via phrases

    processTrackerFrame(metrics, detected, steadyWristRequired);
  }

  function processTrackerFrame(
    metrics: PoseFrameMetrics,
    detected: boolean,
    steadyWristRequired: boolean,
  ) {
    const unstable = steadyWristRequired && wristRef.current.unstable;
    runTrackerFrame(metrics, detected, unstable, steadyWristRequired);
  }

  /** Original hand-landmark frame path — behaviour preserved exactly. */
  function runHandFrame(hand: Landmark[] | undefined) {
    drawOverlay(hand);
    const detected = !!hand;
    setHandDetected(detected);
    statsRef.current.frame(detected);

    const running = runningRef.current;
    if (!hand) {
      noHandFramesRef.current += 1;
      if (running && noHandFramesRef.current > 20) {
        setFeedbackItem({
          level: "error",
          message: "Bring your open hand in front of the camera",
        });
      } else if (!running) {
        setFeedbackItem(null);
      }
      return;
    }
    noHandFramesRef.current = 0;
    const metrics = computeMetrics(hand);
    if (!metrics) return;
    wristRef.current.push(metrics.palmAngleDeg);
    const steadyWristRequired = needsSteadyWrist(exercise.movement_type);
    const unstable = steadyWristRequired && wristRef.current.unstable;

    runTrackerFrame(metrics, detected, unstable, steadyWristRequired);
  }

  /** Shared tracker + feedback step for both hand and pose frames. */
  function runTrackerFrame(
    metrics: FrameMetricsLike,
    detected: boolean,
    unstable: boolean,
    steadyWristRequired: boolean,
  ) {
    const running = runningRef.current;
    const tracker = trackerRef.current;

    if (tracker instanceof HoldTracker) {
      if (!running) return;
      const hold = tracker.update(metrics as PoseFrameMetrics, performance.now());
      const st = HoldTracker.toTrackerState(hold);
      statsRef.current.observe(st.rangeScore, false);
      statsRef.current.onTracker(st);
      setTrackerState(st);
      setFeedbackItem(
        hold.holding
          ? { level: "good", message: `${hold.targetLabel} — ${Math.round(hold.progress * 100)}%` }
          : { level: "warn", message: hold.feedback[0] ?? hold.targetLabel },
      );
      // required hold count reached → finish automatically
      if (!finishedRef.current && hold.holds >= targets.reps) {
        finishedRef.current = true;
        finishSession(hold.holds, true);
      }
      return;
    }

    if (tracker && running) {
      const st = tracker.update(metrics, performance.now());
      statsRef.current.observe(st.rangeScore, unstable);
      statsRef.current.onTracker(st);
      setTrackerState(st);
      setFeedbackItem(
        buildLiveFeedback({
          handDetected: true,
          trackerFeedback: st.feedback,
          targetLabel: tracker.targetLabel,
          rangeScore: st.rangeScore,
          phase: st.phase,
          wristUnstable: unstable,
          steadyWristRequired,
          movementType: exercise.movement_type,
          partLabel,
        }),
      );

      // target reached → finish the session automatically
      if (!finishedRef.current && st.reps >= targets.reps) {
        finishedRef.current = true;
        finishSession(st.reps, true);
        return;
      }
    } else if (!running) {
      // ready phase: skeleton + presence only, no counting
      setTrackerState(null);
      setFeedbackItem(
        detected
          ? {
              level: "good",
              message: poseBased
                ? "Body detected — match the tutorial, then press Start Exercise"
                : "Hand detected — match the tutorial, then press Start Exercise",
            }
          : null,
      );
    }
  }

  async function finishSession(reps: number, completed: boolean) {
    dbg("MEDIA PIPE STOPPED — ending session");
    runningRef.current = false;
    stopCamera();
    const summary = statsRef.current.summary(exercise.movement_type, targets.reps, poseBased ? "Arm" : "Hand");
    setResult(summary);
    setFeedbackItem(completed ? { level: "good", message: "Target complete — well done!" } : null);
    setStep("done");
    try {
      if (sessionRef.current) {
        await api(`/sessions/${sessionRef.current}`, {
          method: "PATCH",
          body: JSON.stringify({
            status: completed ? "completed" : "skipped",
            completed_reps: reps,
            completed_sets: completed ? targets.sets : 1,
            pain_level: painLevel,
            notes: completed
              ? `AI form ${summary.formScore}% (${summary.qualityLabel})`
              : "Ended early via live coach",
          }),
        });
      }
      setSaved("saved");
    } catch {
      setSaved("error");
    }

    // Auto-log the AI-measured metrics to /progress — ONLY on real
    // completion, and only once per session (backend dedupes as well).
    if (completed && sessionRef.current && !progressLoggedRef.current) {
      progressLoggedRef.current = true;
      const durationSeconds = startedAtRef.current
        ? Math.max(1, Math.round((Date.now() - startedAtRef.current) / 1000))
        : null;
      try {
        await api("/progress", {
          method: "POST",
          body: JSON.stringify({
            exercise_session_id: sessionRef.current,
            range_of_motion_deg: summary.romDeg, // null stays null — never faked as 0
            form_score: Math.round(summary.formScore),
            reps_completed: summary.reps,
            duration_seconds: durationSeconds,
          }),
        });
        setLogState("saved");
      } catch {
        setLogState("error");
      }
    } else if (!completed) {
      setLogState("skipped"); // early exit — no progress entry by design
    }
  }

  const reps = trackerState?.reps ?? 0;
  const pct = Math.min(100, Math.round((reps / targets.reps) * 100));
  const formPct = result ? result.formScore : statsRef.current.formPct();
  const qualityLabel = qualityLabelFor(formPct);

  /** Header Back / ✕ — stop everything and leave the session. */
  const endAndClose = useCallback(() => {
    stopCamera();
    onClose();
  }, [stopCamera, onClose]);

  const wide = step === "ready" || step === "run";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-2 md:p-4">
      <div
        className={`flex max-h-[97vh] w-full flex-col overflow-hidden rounded-2xl bg-white shadow-2xl ${
          wide ? "max-w-6xl" : "max-w-xl"
        }`}
      >
        {/* Header */}
        <div className="flex shrink-0 items-center justify-between gap-3 border-b border-slate-200 px-3 py-3 md:px-5">
          <div className="flex min-w-0 items-center gap-2">
            <button
              onClick={endAndClose}
              className="rounded-lg px-2 py-1.5 text-sm font-medium text-slate-500 hover:bg-slate-100"
            >
              ← Back
            </button>
            <div className="min-w-0">
              <h2 className="truncate text-base font-bold text-slate-900 md:text-lg">{exercise.name}</h2>
              {analysisId && (
                <span className="text-[11px] font-medium uppercase tracking-wide text-teal-700">
                  Linked to your report
                </span>
              )}
              <p className="truncate text-xs text-slate-500">
                Upper-Limb Rehab Session · RehabX AI tracks your {meta.targetArea.toLowerCase()} · video stays on
                your device
              </p>
            </div>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <span className="hidden rounded-full bg-teal-50 px-3 py-1 text-xs font-semibold text-teal-700 sm:inline-flex sm:items-center sm:gap-1">
              {meta.areaIcon} {meta.targetArea} rehab
            </span>
            <button
              onClick={endAndClose}
              className="rounded-lg px-2 py-1 text-sm text-slate-500 hover:bg-slate-100"
              aria-label="Close"
            >
              ✕
            </button>
          </div>
        </div>

        {step === "pain" && (
          <div className="mx-auto w-full max-w-md space-y-4 self-center overflow-y-auto px-5 py-6">
            <label className="block text-sm font-medium text-slate-700">
              Aaj ka pain level kitna hai? (0–10)
              <input
                type="range"
                min={0}
                max={10}
                value={painLevel}
                onChange={(e) => setPainLevel(Number(e.target.value))}
                className="mt-2 w-full accent-teal-600"
              />
              <span className="mt-1 block text-center text-2xl font-bold text-teal-700">{painLevel}</span>
            </label>
            <div className="rounded-lg bg-teal-50 px-3 py-2 text-sm text-teal-900">
              Aapka target: <strong>{targets.reps} reps × {targets.sets} set</strong> ({targets.intensity})
              {targets.warning && (
                <p className="mt-1 text-xs font-medium text-amber-700">{targets.warning}</p>
              )}
            </div>
            {cameras.length > 1 && (
              <label className="block text-sm font-medium text-slate-700">
                Camera
                <select
                  value={deviceId}
                  onChange={(e) => setDeviceId(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                >
                  <option value="">Default camera</option>
                  {cameras.map((c) => (
                    <option key={c.value} value={c.value}>
                      {c.label}
                    </option>
                  ))}
                </select>
              </label>
            )}
            <button
              onClick={startSession}
              className="w-full rounded-lg bg-teal-600 px-4 py-2 text-sm font-semibold text-white hover:bg-teal-700"
            >
              Enable Camera &amp; Continue
            </button>
            <p className="text-center text-xs text-slate-400">
              The camera feed is processed on your device — nothing is uploaded.
            </p>
          </div>
        )}

        {(step === "loading" || step === "ready" || step === "run") && (
          <div className="grid flex-1 grid-cols-1 gap-4 overflow-y-auto p-4 md:grid-cols-[minmax(0,1fr)_360px] lg:grid-cols-[minmax(0,1fr)_420px]">
            {/* LEFT — live camera + hand landmarks (primary focus) */}
            <div className="space-y-3">
              <div className="relative overflow-hidden rounded-xl bg-black">
                <video
                  ref={videoRef}
                  autoPlay
                  playsInline
                  muted
                  className="h-auto w-full -scale-x-100"
                />
                <canvas ref={canvasRef} width={640} height={480} className="pointer-events-none absolute inset-0 h-full w-full" />
                {step === "loading" && (
                  <div className="absolute inset-0 flex items-center justify-center bg-black/40 text-sm font-medium text-white">
                    Loading AI tracking model…
                  </div>
                )}
                {step !== "loading" && (
                  <>
                    <div className="absolute right-3 top-3">
                      <span
                        className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold text-white shadow ${
                          handDetected ? "bg-emerald-600/90" : "bg-rose-600/90"
                        }`}
                      >
                        {handDetected
                          ? poseBased
                            ? "🟢 Body Detected"
                            : "🟢 Hand Detected"
                          : poseBased
                            ? "🔴 No Body Detected"
                            : "🔴 No Hand Detected"}
                      </span>
                    </div>
                    {step === "run" ? (
                      <div className="absolute left-3 top-3 rounded-lg bg-white/90 px-3 py-2 shadow">
                        <span className="text-2xl font-bold text-teal-700">{reps}</span>
                        <span className="text-sm text-slate-600"> / {targets.reps} reps</span>
                        <div className="mt-1 h-1.5 w-36 overflow-hidden rounded-full bg-slate-200">
                          <div className="h-full rounded-full bg-teal-600 transition-all" style={{ width: `${pct}%` }} />
                        </div>
                      </div>
                    ) : (
                      <div className="absolute left-3 top-3 rounded-lg bg-white/90 px-3 py-1.5 text-xs font-semibold text-slate-700 shadow">
                        🎯 Target: {targets.reps} reps{meta.holdSeconds ? ` · hold ${meta.holdSeconds}s` : ""}
                      </div>
                    )}
                    {feedbackItem && (
                      <div
                        className={`absolute inset-x-3 bottom-3 rounded-lg px-3 py-2 text-center text-sm font-semibold text-white shadow-lg backdrop-blur-sm ${
                          feedbackItem.level === "good"
                            ? "bg-emerald-600/85"
                            : feedbackItem.level === "warn"
                              ? "bg-amber-500/90"
                              : "bg-rose-600/90"
                        }`}
                      >
                        {LEVEL_DOT[feedbackItem.level]} {feedbackItem.message}
                      </div>
                    )}
                  </>
                )}
              </div>

              {/* live stat strip */}
              <div className={`grid grid-cols-3 gap-2 transition-opacity ${step === "run" ? "opacity-100" : "opacity-40"}`}>
                <StatCard label="Form Score" value={`${formPct}%`} />
                <StatCard label="Movement Quality" value={qualityLabel} />
                <StatCard
                  label="Incorrect Reps"
                  value={`${result ? result.incorrectReps : statsRef.current.incorrectReps()}`}
                />
              </div>

              {step === "ready" && (
                <div className="space-y-1.5">
                  <button
                    onClick={beginExercise}
                    disabled={!handDetected}
                    className="w-full rounded-xl bg-teal-600 px-4 py-3 text-base font-bold text-white shadow transition-colors hover:bg-teal-700 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    ▶ Start Exercise
                  </button>
                  <p className="text-center text-xs text-slate-500">
                    {handDetected
                      ? "AI is watching — rep counting and feedback begin when you start."
                      : poseBased
                        ? "Stand back so your arm and torso are visible to enable."
                        : "Show your open hand to the camera to enable."}
                  </p>
                </div>
              )}
              {step === "run" && (
                <button
                  onClick={() => finishSession(reps, false)}
                  className="w-full rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
                >
                  End session early
                </button>
              )}
            </div>

            {/* RIGHT — exercise tutorial + guidance */}
            <aside className="space-y-4 md:border-l md:border-slate-100 md:pl-4">
              <section>
                <h3 className="mb-2 text-xs font-bold uppercase tracking-wider text-slate-400">
                  Exercise Tutorial · {exercise.name}
                </h3>
                <ExerciseTutorial
                  src={meta.tutorialVideo}
                  slug={exercise.slug}
                  label={exercise.name}
                  autoPlay
                />
              </section>

              <section>
                <h3 className="mb-2 text-xs font-bold uppercase tracking-wider text-slate-400">How to perform</h3>
                <ol className="space-y-2">
                  {instructions.map((s, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm text-slate-700">
                      <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-teal-600 text-[11px] font-bold text-white">
                        {i + 1}
                      </span>
                      <span>{s}</span>
                    </li>
                  ))}
                </ol>
              </section>

              <section className="grid grid-cols-3 gap-2">
                <StatCard label="Recommended" value={`${meta.recommendedReps} reps`} />
                <StatCard label="Hold" value={meta.holdSeconds ? `${meta.holdSeconds}s` : "—"} />
                <StatCard label="Difficulty" value={difficultyLabel(exercise.difficulty, exercise.slug)} />
              </section>

              <section>
                <h3 className="mb-2 text-xs font-bold uppercase tracking-wider text-slate-400">
                  AI tracks these landmarks
                </h3>
                <div className="flex flex-wrap gap-1.5">
                  {meta.targetLandmarks.map((l) => (
                    <span key={l} className="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs text-slate-600">
                      {l}
                    </span>
                  ))}
                </div>
              </section>

              {safetyTips.length > 0 && (
                <section className="rounded-xl border border-amber-200 bg-amber-50 p-3">
                  <h3 className="text-xs font-bold uppercase tracking-wide text-amber-800">⚠⚠️ Safety Tip</h3>
                  <ul className="mt-1.5 space-y-1 text-sm text-amber-900">
                    {safetyTips.map((t) => (
                      <li key={t} className="flex gap-1.5">
                        <span aria-hidden>•</span>
                        <span>{t}</span>
                      </li>
                    ))}
                  </ul>
                </section>
              )}
            </aside>
          </div>
        )}

        {step === "done" && result && (
          <div className="mx-auto w-full max-w-md space-y-4 self-center overflow-y-auto px-5 py-6">
            <div className={`rounded-xl px-4 py-5 text-center ${reps >= targets.reps ? "bg-emerald-50" : "bg-slate-50"}`}>
              <p className="text-3xl">{reps >= targets.reps ? "🎉" : "🫱"}</p>
              <h3 className={`mt-1 text-lg font-bold ${reps >= targets.reps ? "text-emerald-800" : "text-slate-800"}`}>
                {reps >= targets.reps ? "Exercise Complete 🎉" : "Session Ended"}
              </h3>
              <p className={`text-sm ${reps >= targets.reps ? "text-emerald-700" : "text-slate-500"}`}>
                {exercise.name} · pain level {painLevel}/10
              </p>
            </div>

            <dl className="overflow-hidden rounded-xl border border-slate-200 text-sm">
              <ResultRow label="Repetitions" value={`${result.reps} / ${result.plannedReps}`} />
              <ResultRow label="Form Score" value={`${result.formScore}%`} />
              <ResultRow
                label="Movement Quality"
                value={result.qualityLabel}
                tone={result.qualityLabel === "Good" ? "good" : result.qualityLabel === "Fair" ? "warn" : "bad"}
              />
              <ResultRow
                label="AI-Measured ROM"
                value={result.romDeg !== null ? `≈${result.romDeg}°` : "Not measured"}
              />
              <ResultRow
                label="Duration"
                value={durationLabel(startedAtRef.current)}
              />
              <ResultRow label="Pain" value={`${painLevel}/10`} />
            </dl>

            <div className="rounded-xl bg-slate-50 p-3">
              <h4 className="text-xs font-bold uppercase tracking-wide text-slate-500">AI Feedback</h4>
              <ul className="mt-1.5 space-y-1">
                {result.checklist.map((c) => (
                  <li key={c.text} className={`flex gap-2 text-sm ${c.ok ? "text-slate-700" : "text-amber-700"}`}>
                    <span aria-hidden>{c.ok ? "✓" : "⚠"}</span>
                    <span>{c.text}</span>
                  </li>
                ))}
              </ul>
            </div>

            <p className="text-center text-xs text-slate-500">
              {logState === "saved"
                ? saved === "saved"
                  ? "Your progress has been saved."
                  : "Metrics saved — session note could not be stored."
                : logState === "error"
                  ? "Could not save the progress entry."
                  : logState === "skipped"
                    ? "Ended early — nothing was added to your progress."
                    : saved === "error"
                      ? "Could not save the session."
                      : "Saving…"}
            </p>
            <button
              onClick={onClose}
              className="w-full rounded-lg bg-teal-600 px-4 py-2 text-sm font-semibold text-white hover:bg-teal-700"
            >
              Done
            </button>
          </div>
        )}

        {step === "error" && (
          <div className="mx-auto w-full max-w-md space-y-4 self-center px-5 py-6">
            <div className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">{errorMsg}</div>
            {camDiag && (
              <details className="rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-600">
                <summary className="cursor-pointer font-medium">Technical details (debugging)</summary>
                <pre className="mt-2 whitespace-pre-wrap break-all">{JSON.stringify(camDiag, null, 2)}</pre>
              </details>
            )}
            <button
              onClick={startSession}
              className="w-full rounded-lg bg-teal-600 px-4 py-2 text-sm font-semibold text-white hover:bg-teal-700"
            >
              Retry
            </button>
            <button
              onClick={() => setStep("pain")}
              className="w-full rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium hover:bg-slate-50"
            >
              Back
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

/** mm:ss wall-clock duration of the active exercise, "—" when unknown. */
function durationLabel(startedAt: number | null): string {
  if (!startedAt) return "—";
  const s = Math.max(1, Math.round((Date.now() - startedAt) / 1000));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

/** Small labelled stat tile used under the camera and in the tutorial column. */
function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white px-2 py-2 text-center shadow-sm">
      <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">{label}</p>
      <p className="truncate text-base font-bold text-slate-800">{value}</p>
    </div>
  );
}

/** One label/value row of the results card. */
function ResultRow({ label, value, tone }: { label: string; value: string; tone?: "good" | "warn" | "bad" }) {
  const toneClass =
    tone === "good"
      ? "bg-emerald-100 text-emerald-700"
      : tone === "warn"
        ? "bg-amber-100 text-amber-700"
        : tone === "bad"
          ? "bg-rose-100 text-rose-700"
          : "";
  return (
    <div className="flex items-center justify-between border-b border-slate-100 px-3 py-2 last:border-b-0">
      <dt className="text-slate-500">{label}</dt>
      <dd className={`font-bold text-slate-800 ${tone ? `rounded-full px-2.5 py-0.5 ${toneClass}` : ""}`}>{value}</dd>
    </div>
  );
}
