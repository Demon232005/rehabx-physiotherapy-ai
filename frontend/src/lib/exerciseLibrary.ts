/**
 * RehabX AI — hand & upper-limb rehabilitation exercise metadata.
 *
 * The backend (`GET /api/v1/exercises`) remains the source of truth for the
 * clinical rows (name, dosage, contraindications…). This module layers the
 * client-side tutorial/coaching metadata onto those rows: which tutorial video
 * to play, step-by-step instructions, hold durations, the hand landmarks the
 * AI focuses on, and safety tips.
 */

export interface HandExerciseMeta {
  /** display grouping: Fingers | Thumb | Wrist | Forearm | Elbow */
  targetArea: string;
  areaIcon: string;
  difficulty: "Beginner" | "Intermediate";
  /** dynamically resolved per exercise: /tutorials/<slug>.mp4 */
  tutorialVideo: string;
  instructions: string[];
  recommendedReps: number;
  /** seconds to hold the end position, when applicable */
  holdSeconds: number | null;
  /** hand joints/landmarks the AI tracks for this exercise */
  targetLandmarks: string[];
  safetyTips: string[];
}

const FINGERS_LANDMARKS = [
  "Fingertips (index·middle·ring·little)",
  "Finger PIP / DIP joints",
  "Knuckles (MCP)",
  "Wrist",
];

const THUMB_LANDMARKS = [
  "Thumb tip",
  "Thumb IP / MCP joints",
  "Thumb base (CMC)",
  "Index fingertip",
];

const WRIST_LANDMARKS = [
  "Wrist centre",
  "Knuckle line (MCP)",
  "Fingertip centroid",
];

const FOREARM_LANDMARKS = [
  "Palm orientation angle",
  "Wrist centre",
  "Middle knuckle (MCP)",
];

/**
 * Full hand-rehabilitation catalogue. Keys match backend slugs one-to-one so
 * any `ExerciseOut` row can be enriched with `getExerciseMeta(slug)`.
 */
export const HAND_EXERCISE_LIBRARY: Record<string, HandExerciseMeta> = {
  "finger-flexion": {
    targetArea: "Fingers",
    areaIcon: "✋",
    difficulty: "Beginner",
    tutorialVideo: "/tutorials/finger-flexion.mp4",
    instructions: [
      "Rest your forearm on a table, palm facing up",
      "Keep your wrist straight and still",
      "Slowly bend your fingers into a gentle fist",
      "Hold briefly, then slowly open your hand",
    ],
    recommendedReps: 10,
    holdSeconds: 3,
    targetLandmarks: FINGERS_LANDMARKS,
    safetyTips: [
      "Don't force the fingers — movement must stay pain-free",
      "Stop immediately if you feel sharp joint pain",
    ],
  },
  "finger-extension": {
    targetArea: "Fingers",
    areaIcon: "🖐️",
    difficulty: "Beginner",
    tutorialVideo: "/tutorials/finger-extension.mp4",
    instructions: [
      "Start with the fingers gently bent",
      "Slowly straighten and lift the fingers",
      "Open the hand fully without strain",
      "Relax back and repeat",
    ],
    recommendedReps: 10,
    holdSeconds: 2,
    targetLandmarks: FINGERS_LANDMARKS,
    safetyTips: [
      "Never hyper-extend into a locked joint",
      "Reduce the range if the knuckles catch or click",
    ],
  },
  "finger-spreading": {
    targetArea: "Fingers",
    areaIcon: "✋",
    difficulty: "Beginner",
    tutorialVideo: "/tutorials/finger-spreading.mp4",
    instructions: [
      "Lay your palm flat with the fingers together",
      "Spread the fingers apart comfortably",
      "Hold the open position briefly",
      "Bring the fingers back together",
    ],
    recommendedReps: 10,
    holdSeconds: 3,
    targetLandmarks: ["Fingertip spacing", "Knuckles (MCP)", "Wrist"],
    safetyTips: ["Avoid forced spreading into the web-spaces"],
  },
  "finger-walking": {
    targetArea: "Fingers",
    areaIcon: "🚶",
    difficulty: "Intermediate",
    tutorialVideo: "/tutorials/finger-walking.mp4",
    instructions: [
      "Place your palm flat on a table",
      "Lift and place one finger at a time",
      "'Walk' your hand forward across the table",
      "Walk the hand back to the start",
    ],
    recommendedReps: 8,
    holdSeconds: null,
    targetLandmarks: FINGERS_LANDMARKS,
    safetyTips: ["Skip if the knuckle joints are painful today"],
  },
  "fist-open-close": {
    targetArea: "Fingers",
    areaIcon: "✊",
    difficulty: "Beginner",
    tutorialVideo: "/tutorials/fist-open-close.mp4",
    instructions: [
      "Support your forearm with the hand relaxed",
      "Close into a gentle full fist",
      "Keep the thumb wrapped outside the fingers",
      "Open the hand fully, then repeat",
    ],
    recommendedReps: 10,
    holdSeconds: 3,
    targetLandmarks: [...FINGERS_LANDMARKS, "Thumb tip"],
    safetyTips: [
      "No tight fists in early healing or acute pain",
      "Avoid entirely with a suspected fracture",
    ],
  },
  "thumb-opposition": {
    targetArea: "Thumb",
    areaIcon: "👍",
    difficulty: "Beginner",
    tutorialVideo: "/tutorials/thumb-opposition.mp4",
    instructions: [
      "Hold your palm facing up",
      "Touch the thumb to the index fingertip",
      "Continue across middle, ring and little finger",
      "Reverse the sequence back down",
    ],
    recommendedReps: 8,
    holdSeconds: 2,
    targetLandmarks: THUMB_LANDMARKS,
    safetyTips: ["Avoid if the thumb base joint is swollen or acutely painful"],
  },
  "thumb-flexion": {
    targetArea: "Thumb",
    areaIcon: "👍",
    difficulty: "Beginner",
    tutorialVideo: "/tutorials/thumb-flexion.mp4",
    instructions: [
      "Rest your hand palm-up, fully relaxed",
      "Reach the thumb across the palm",
      "Touch near the base of the little finger",
      "Return the thumb slowly outward",
    ],
    recommendedReps: 10,
    holdSeconds: 3,
    targetLandmarks: THUMB_LANDMARKS,
    safetyTips: ["Never force the movement at the thumb base (CMC) joint"],
  },
  "thumb-extension": {
    targetArea: "Thumb",
    areaIcon: "👍",
    difficulty: "Beginner",
    tutorialVideo: "/tutorials/thumb-extension.mp4",
    instructions: [
      "Hand resting flat, fingers relaxed",
      "Move the thumb out and away from the palm",
      "Hold the stretched position briefly",
      "Return the thumb alongside the hand",
    ],
    recommendedReps: 10,
    holdSeconds: 3,
    targetLandmarks: THUMB_LANDMARKS,
    safetyTips: ["Stop if pain radiates along the thumb side of the wrist"],
  },
  "thumb-abduction": {
    targetArea: "Thumb",
    areaIcon: "👍",
    difficulty: "Beginner",
    tutorialVideo: "/tutorials/thumb-abduction.mp4",
    instructions: [
      "Hand flat with the palm facing up",
      "Lift the thumb straight away from the fingers",
      "Hold the open web-space briefly",
      "Return the thumb gently alongside",
    ],
    recommendedReps: 10,
    holdSeconds: 3,
    targetLandmarks: THUMB_LANDMARKS,
    safetyTips: ["Do not force the thumb backwards"],
  },
  "wrist-flexion": {
    targetArea: "Wrist",
    areaIcon: "🔄",
    difficulty: "Beginner",
    tutorialVideo: "/tutorials/wrist-flexion.mp4",
    instructions: [
      "Forearm supported on a table, hand free at the edge",
      "Keep the fingers relaxed",
      "Bend the hand down at the wrist",
      "Lift back up within a pain-free range",
    ],
    recommendedReps: 12,
    holdSeconds: 3,
    targetLandmarks: WRIST_LANDMARKS,
    safetyTips: [
      "Avoid end-range stretching soon after injury",
      "The forearm stays still — only the wrist moves",
    ],
  },
  "wrist-extension": {
    targetArea: "Wrist",
    areaIcon: "🔄",
    difficulty: "Beginner",
    tutorialVideo: "/tutorials/wrist-extension.mp4",
    instructions: [
      "Forearm supported, palm facing down",
      "Raise your wrist slightly higher, lifting the back of the hand",
      "Stop at a mild stretch",
      "Lower slowly and repeat",
    ],
    recommendedReps: 12,
    holdSeconds: 3,
    targetLandmarks: WRIST_LANDMARKS,
    safetyTips: ["Avoid if it reproduces sharp pain on the back of the wrist"],
  },
  "wrist-rotation": {
    targetArea: "Wrist",
    areaIcon: "🌀",
    difficulty: "Beginner",
    tutorialVideo: "/tutorials/wrist-rotation.mp4",
    instructions: [
      "Elbow bent at 90°, hand relaxed",
      "Circle the hand clockwise, slowly",
      "Keep the forearm still throughout",
      "Repeat anticlockwise after a pause",
    ],
    recommendedReps: 8,
    holdSeconds: null,
    targetLandmarks: WRIST_LANDMARKS,
    safetyTips: ["Avoid fast circles during acute inflammation"],
  },
  "wrist-ulnar-radial-deviation": {
    targetArea: "Wrist",
    areaIcon: "↔️",
    difficulty: "Beginner",
    tutorialVideo: "/tutorials/wrist-ulnar-radial-deviation.mp4",
    instructions: [
      "Hand resting on its side, thumb pointing up",
      "Tip the hand toward the little finger",
      "Return through the middle",
      "Tip toward the thumb side",
    ],
    recommendedReps: 10,
    holdSeconds: 2,
    targetLandmarks: WRIST_LANDMARKS,
    safetyTips: ["Stay clear of painful end-range near the ulnar styloid"],
  },
  "wrist-ulnar-deviation": {
    targetArea: "Wrist",
    areaIcon: "➡️",
    difficulty: "Beginner",
    tutorialVideo: "/tutorials/wrist-ulnar-deviation.mp4",
    instructions: [
      "Forearm supported, thumb pointing up",
      "Tip the hand toward the little finger",
      "Stay within a comfortable arc",
      "Return upright slowly",
    ],
    recommendedReps: 10,
    holdSeconds: 2,
    targetLandmarks: WRIST_LANDMARKS,
    safetyTips: ["Stop if you feel clicking together with pain"],
  },
  "wrist-radial-deviation": {
    targetArea: "Wrist",
    areaIcon: "⬅️",
    difficulty: "Beginner",
    tutorialVideo: "/tutorials/wrist-radial-deviation.mp4",
    instructions: [
      "Forearm supported, thumb pointing up",
      "Tip the hand toward the thumb side",
      "Keep the motion small and smooth",
      "Return to the middle",
    ],
    recommendedReps: 10,
    holdSeconds: 2,
    targetLandmarks: WRIST_LANDMARKS,
    safetyTips: ["Avoid if pain runs along the thumb side of the wrist"],
  },
  "gentle-grip-release": {
    targetArea: "Grip",
    areaIcon: "🎾",
    difficulty: "Intermediate",
    tutorialVideo: "/tutorials/gentle-grip-release.mp4",
    instructions: [
      "Hold a soft ball or rolled sock",
      "Squeeze gently — never to the point of pain",
      "Hold the squeeze for about 3 seconds",
      "Release fully and open the hand",
    ],
    recommendedReps: 10,
    holdSeconds: 5,
    targetLandmarks: [...FINGERS_LANDMARKS, "Thumb tip"],
    safetyTips: [
      "Not during acute pain or a suspected fracture",
      "Skip if gripping causes joint pain",
    ],
  },
  "towel-wring": {
    targetArea: "Forearm",
    areaIcon: "🧻",
    difficulty: "Intermediate",
    tutorialVideo: "/tutorials/towel-wring.mp4",
    instructions: [
      "Hold a rolled towel with both hands",
      "Twist one hand toward you",
      "Twist the other hand away",
      "Reverse directions and repeat",
    ],
    recommendedReps: 6,
    holdSeconds: null,
    targetLandmarks: [...FOREARM_LANDMARKS, "Both hands"],
    safetyTips: ["Not for acute injuries — skip if it reproduces wrist pain"],
  },
  "individual-finger-flexion": {
    targetArea: "Fingers",
    areaIcon: "☝️",
    difficulty: "Beginner",
    tutorialVideo: "/tutorials/individual-finger-flexion.mp4",
    instructions: [
      "Palm facing up, fingers fully relaxed",
      "Bend one finger down into the palm",
      "Straighten it fully before the next",
      "Work through every finger in turn",
    ],
    recommendedReps: 6,
    holdSeconds: 2,
    targetLandmarks: FINGERS_LANDMARKS,
    safetyTips: [
      "Never force a stiff joint into sharp pain",
      "Only after tendon-repair clearance from your clinician",
    ],
  },
  "tendon-gliding": {
    targetArea: "Fingers",
    areaIcon: "🤲",
    difficulty: "Intermediate",
    tutorialVideo: "/tutorials/tendon-gliding.mp4",
    instructions: [
      "Start with a straight hand",
      "Bend into a hook fist",
      "Form a table-top at 90 degrees",
      "Finish into a full fist — then reverse",
    ],
    recommendedReps: 6,
    holdSeconds: 2,
    targetLandmarks: FINGERS_LANDMARKS,
    safetyTips: [
      "Reduce the range if tendons catch or lock",
      "Not during acute tendon repair without surgeon approval",
    ],
  },
  "forearm-pronation": {
    targetArea: "Forearm",
    areaIcon: "🔃",
    difficulty: "Beginner",
    tutorialVideo: "/tutorials/forearm-pronation.mp4",
    instructions: [
      "Elbow bent at 90°, tucked against your side",
      "Start with the thumb pointing up",
      "Rotate slowly so the palm faces the floor",
      "Hold briefly, then rotate back up",
    ],
    recommendedReps: 10,
    holdSeconds: 3,
    targetLandmarks: FOREARM_LANDMARKS,
    safetyTips: ["Keep the elbow still — don't swing the arm"],
  },
  "forearm-supination": {
    targetArea: "Forearm",
    areaIcon: "🔃",
    difficulty: "Beginner",
    tutorialVideo: "/tutorials/forearm-supination.mp4",
    instructions: [
      "Elbow bent at 90°, tucked against your side",
      "Start with the palm facing down",
      "Rotate slowly so the palm faces the ceiling",
      "Hold briefly, then rotate back down",
    ],
      recommendedReps: 10,
      holdSeconds: 3,
      targetLandmarks: FOREARM_LANDMARKS,
      safetyTips: ["Don't shrug the shoulder as you rotate"],
  },
  "elbow-flexion-extension": {
    targetArea: "Elbow",
    areaIcon: "💪",
    difficulty: "Beginner",
    tutorialVideo: "/tutorials/elbow-flexion-extension.mp4",
    instructions: [
      "Sit tall with the arm at your side",
      "Bend the elbow, bringing the hand toward the shoulder",
      "Keep the upper arm still",
      "Straighten the elbow slowly",
    ],
    recommendedReps: 10,
    holdSeconds: 3,
    targetLandmarks: ["Wrist height", "Hand elevation", "Palm orientation"],
    safetyTips: [
      "Never force past the point of sharp pain",
      "Only light movement until fracture clearance",
    ],
  },
};

/** Enrichment for ANY exercise row — unknown slugs get safe defaults. */
export function getExerciseMeta(slug: string): HandExerciseMeta {
  return (
    HAND_EXERCISE_LIBRARY[slug] ?? {
      targetArea: "Hand",
      areaIcon: "✋",
      difficulty: "Beginner",
      tutorialVideo: `/tutorials/${slug}.mp4`,
      instructions: [],
      recommendedReps: 10,
      holdSeconds: null,
      targetLandmarks: ["Wrist", "Fingers", "Thumb"],
      safetyTips: ["Move only within a pain-free range"],
    }
  );
}

// ---------------------------------------------------------------------------
// Upper-limb platform: region registry + row-derived enrichment
// ---------------------------------------------------------------------------

/** Display identity for every supported body area across the platform. */
export const REGION_META: Record<string, { label: string; icon: string }> = {
  hand: { label: "Hand & Fingers", icon: "✋" },
  fingers: { label: "Fingers", icon: "🖐️" },
  thumb: { label: "Thumb", icon: "👍" },
  palm: { label: "Palm", icon: "🤲" },
  grip: { label: "Grip", icon: "✊" },
  wrist: { label: "Wrist", icon: "🔄" },
  forearm: { label: "Forearm", icon: "💪" },
  elbow: { label: "Elbow", icon: "🎯" },
  shoulder: { label: "Shoulder", icon: "🙆" },
};

/** Canonical ordering for filter chips in the library UI. */
export const CANONICAL_REGIONS = [
  "hand",
  "thumb",
  "palm",
  "grip",
  "wrist",
  "forearm",
  "elbow",
  "shoulder",
];

export const CATEGORY_META: Record<string, { label: string; icon: string }> = {
  mobility: { label: "Mobility", icon: "🔄" },
  stretching: { label: "Stretching", icon: "🧘" },
  strengthening: { label: "Strengthening", icon: "💪" },
  recovery: { label: "Recovery", icon: "🌿" },
};

export type TrackingMode = "hand" | "pose" | "hand+pose";

/**
 * Which AI models does an exercise need? Explicit declaration wins;
 * legacy rows fall back to a conservative per-region default.
 */
export function resolveTrackingMode(exercise: {
  tracking_mode?: string | null;
  target_region?: string;
}): TrackingMode {
  if (
    exercise.tracking_mode === "hand" ||
    exercise.tracking_mode === "pose" ||
    exercise.tracking_mode === "hand+pose"
  ) {
    return exercise.tracking_mode;
  }
  return deriveTrackingMode(exercise.target_region ?? "hand");
}

function deriveTrackingMode(region: string): TrackingMode {
  switch (region) {
    case "elbow":
    case "shoulder":
      return "pose";
    case "wrist":
    case "forearm":
      // legacy rows tracked these with hand landmarks (proven pipeline)
      return "hand";
    default:
      return "hand";
  }
}

const POSE_LANDMARK_SETS: Record<string, string[]> = {
  elbow: ["Shoulder joint", "Elbow joint (3-point angle)", "Wrist centre"],
  shoulder: ["Both shoulders", "Elbow joints", "Wrists", "Hip reference line"],
  wrist: ["Pose: elbow → wrist axis", "Hand: knuckle direction", "Forearm stability"],
  forearm: ["Pose: arm segments", "Hand: palm orientation"],
};

function landmarksForRow(
  mode: TrackingMode,
  region: string,
  movementType: string
): string[] {
  if (mode === "pose") return POSE_LANDMARK_SETS[region] ?? POSE_LANDMARK_SETS.shoulder;
  if (mode === "hand+pose") return POSE_LANDMARK_SETS.wrist;
  if (region === "thumb") return THUMB_LANDMARKS;
  if (region === "wrist") return WRIST_LANDMARKS;
  if (region === "forearm") return FOREARM_LANDMARKS;
  if (movementType.startsWith("shoulder")) return POSE_LANDMARK_SETS.shoulder;
  return FINGERS_LANDMARKS;
}

/**
 * Full enrichment for any ExerciseOut row — curated hand-rehab data when it
 * exists, otherwise everything derived from the row itself so every new
 * upper-limb exercise works without duplicated definitions.
 */
export function getExerciseMetaForRow(
  exercise: Pick<
    ExerciseRow,
    | "slug" | "target_region" | "tracking_mode" | "difficulty" | "rep_range_max"
    | "starting_position" | "required_movement" | "contraindications" | "movement_type"
  >,
): HandExerciseMeta {
  const curated = HAND_EXERCISE_LIBRARY[exercise.slug];
  const mode = resolveTrackingMode(exercise);
  const regionMeta = REGION_META[exercise.target_region] ?? REGION_META.hand;
  const cautions = exercise.contraindications ?? [];

  return {
    targetArea: curated?.targetArea ?? regionMeta.label,
    areaIcon: curated?.areaIcon ?? regionMeta.icon,
    difficulty:
      curated?.difficulty ??
      (exercise.difficulty === "intermediate"
        ? "Intermediate"
        : exercise.difficulty === "advanced"
          ? "Advanced"
          : "Beginner"),
    tutorialVideo: `/tutorials/${exercise.slug}.mp4`,
    instructions:
      curated && curated.instructions.length > 0
        ? curated.instructions
        : [exercise.starting_position, exercise.required_movement].filter(
            (s): s is string => Boolean(s),
          ),
    recommendedReps: curated?.recommendedReps ?? exercise.rep_range_max ?? 10,
    holdSeconds: curated?.holdSeconds ?? null,
    targetLandmarks:
      curated && curated.targetLandmarks.length > 0
        ? curated.targetLandmarks
        : landmarksForRow(mode, exercise.target_region, exercise.movement_type),
    safetyTips:
      curated && curated.safetyTips.length > 0
        ? [...new Set([...curated.safetyTips, ...cautions])].slice(0, 3)
        : cautions.slice(0, 2).length > 0
          ? cautions.slice(0, 2)
          : ["Move only within a pain-free range"],
  };
}

/** Minimal structural type so this module stays decoupled from api/types. */
interface ExerciseRow {
  slug: string;
  target_region: string;
  tracking_mode?: string | null;
  difficulty?: string;
  rep_range_max?: number;
  starting_position?: string;
  required_movement?: string;
  contraindications?: string[];
  movement_type: string;
}

/** Difficulty label for backend's lowercase value, falling back to meta. */
export function difficultyLabel(value: string | undefined, slug: string): string {
  if (value === "beginner") return "Beginner";
  if (value === "intermediate") return "Intermediate";
  if (value === "advanced") return "Advanced";
  return getExerciseMeta(slug).difficulty;
}
