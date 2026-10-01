// TypeScript mirrors of the backend Pydantic schemas (backend/app/schemas/__init__.py)

export interface UserOut {
  id: string;
  email: string;
  full_name: string;
  role: string;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export interface ReportParsed {
  affected_side: string | null;
  affected_region: string | null;
  /** Upper-limb hierarchy refinement from the report (null = not stated). */
  sub_region?: string | null;
  specific_structure?: string | null;
  severity: string | null;
  condition: string | null;
  condition_label: string | null;
  summary: string;
  matched_terms: Record<string, any>;
  confidence: Record<string, number>;
  /** Precautions explicitly stated in the report — never invented. */
  restrictions?: { restriction: string; matched_term: string }[];
  /** One entry per reported injury (supports multiple injuries). */
  findings?: Record<string, any>[];
  /** e.g. "left_index_finger" — the area rehabilitation is scoped to. */
  recommended_region?: string | null;
  source: string;
}

export interface ReportFileParsedOut {
  filename: string;
  text: string;
  parsed: ReportParsed;
}

export interface UploadOut {
  id: string;
  original_filename: string;
  content_type: string;
  file_size_bytes: number;
  image_width: number | null;
  image_height: number | null;
  affected_side: string | null;
  affected_region: string | null;
  xray_report: string | null;
  report_parsed: ReportParsed | null;
  status: string;
  created_at: string;
}

export interface DetectedRegionOut {
  id: string;
  label: string;
  region_type: string;
  bbox_x: number | null;
  bbox_y: number | null;
  bbox_w: number | null;
  bbox_h: number | null;
  confidence: number;
  detection_method: string;
}

export interface AnalysisOut {
  id: string;
  upload_id: string;
  model_name: string;
  model_version: string;
  model_status: string;
  prediction_label: string;
  confidence: number;
  class_probabilities: Record<string, number>;
  findings: Record<string, unknown>;
  preprocessing: Record<string, unknown> | null;
  analysis_duration_ms: number | null;
  status: string;
  created_at: string;
  regions: DetectedRegionOut[];
}

export interface AnalysisDetailOut extends AnalysisOut {
  upload: UploadOut | null;
}

export interface RecommendedCategoryOut {
  key: string;
  label: string;
  description: string;
  exercises?: ExerciseOut[];
  /** Report-driven section metadata (engine v2). */
  target_side?: string | null;
  target_region?: string | null;
  sub_region?: string | null;
  specific_structure?: string | null;
  condition?: string | null;
  condition_label?: string | null;
  severity?: string | null;
  status?: "ok" | "needs_clarification" | "not_safe";
  message?: string | null;
}

export interface RecommendationOut {
  id: string;
  analysis_id: string;
  rehab_focus: string;
  affected_region: string;
  affected_side: string;
  abnormality_category: string;
  focus_reasoning: string[];
  recommended_exercise_categories: RecommendedCategoryOut[];
  movement_requirements: string[];
  repetition_guidance: Record<string, unknown>;
  session_structure: Record<string, unknown>;
  safety_warnings: string[];
  disclaimer: string;
  engine_version: string;
  /** Structured report extraction that produced this plan (engine v2). */
  extraction?: Record<string, any> | null;
  created_at: string;
}

export interface ExerciseOut {
  id: string;
  slug: string;
  name: string;
  description: string;
  target_region: string;
  movement_type: string;
  starting_position: string;
  required_movement: string;
  contraindications: string[];
  difficulty: string;
  rep_range_min: number;
  rep_range_max: number;
  set_range_min: number;
  set_range_max: number;
  animation_placeholder: string | null;
  /** Upper-limb platform metadata (null on legacy rows until reseeded). */
  category?: string | null; // mobility|stretching|strengthening|recovery
  tracking_mode?: string | null; // hand|pose|hand+pose
  duration_minutes?: number | null;
  progression_level?: number | null;
}

export interface ExerciseSessionOut {
  id: string;
  exercise_id: string;
  analysis_id: string | null;
  planned_reps: number | null;
  planned_sets: number | null;
  completed_reps: number | null;
  completed_sets: number | null;
  status: string;
  pain_level: number | null;
  notes: string | null;
  completed_at: string | null;
  created_at: string;
  exercise: ExerciseOut | null;
  /** Laterality snapshot from the driving report (spec §18). */
  affected_side?: string | null;
  body_region?: string | null;
  specific_structure?: string | null;
}

export interface ProgressOut {
  id: string;
  analysis_id: string | null;
  date: string;
  pain_level: number | null;
  grip_strength_kg: number | null;
  range_of_motion_deg: number | null;
  self_reported_improvement: number | null;
  notes: string | null;
  /** Auto-logged session metrics (null on manual entries). */
  exercise_session_id?: string | null;
  form_score?: number | null;
  reps_completed?: number | null;
  duration_seconds?: number | null;
  source?: string; // manual | session
  /** Laterality snapshot copied from the session's driving report. */
  affected_side?: string | null;
  body_region?: string | null;
  specific_structure?: string | null;
}

export interface ReportOut {
  upload_id: string;
  analysis: AnalysisOut;
  recommendation: RecommendationOut;
  detected_regions: DetectedRegionOut[];
  report_text: string;
  disclaimer: string;
}

export interface DashboardOut {
  recent_analyses: AnalysisDetailOut[];
  latest_analysis: AnalysisDetailOut | null;
  latest_recommendation: RecommendationOut | null;
  total_analyses: number;
  total_sessions_completed: number;
  upcoming_sessions: ExerciseSessionOut[];
  progress_entries: ProgressOut[];
  exercise_count: number;
}

export interface MessageOut {
  message: string;
}

export interface ApiError {
  detail?: string | { msg: string }[];
}

export interface AdminStatsOut {
  total_users: number;
  total_analyses: number;
  total_uploads: number;
  total_exercises: number;
  total_sessions: number;
  users_by_role: Record<string, number>;
  analyses_by_status: Record<string, number>;
}

export interface UserListOut {
  id: string;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
  created_at: string;
}

export interface AuditLogOut {
  id: string;
  user_id: string;
  action: string;
  entity: string | null;
  entity_id: string | null;
  ip_address: string | null;
  created_at: string;
}

export interface AuditLogListOut {
  items: AuditLogOut[];
  total: number;
}

export interface PasswordResetRequest {
  email: string;
}

export interface PasswordResetConfirm {
  token: string;
  new_password: string;
}
