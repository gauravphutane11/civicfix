export interface AuthUser {
  id: number;
  name: string;
  email: string | null;
  phone: string | null;
  role: string;
  department: string | null;
  service_category: string | null;
  availability_status: string | null;
  is_active: boolean;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: AuthUser;
}

export interface CitizenOtpRequestResponse {
  message: string;
  expires_in_seconds: number;
  retry_after_seconds: number;
  demo_otp: string | null;
  is_new_user: boolean;
  delivery_mode: string;
}

export type IssueCategory =
  | "pothole"
  | "garbage"
  | "streetlight"
  | "drainage"
  | "road_infrastructure"
  | "water_supply"
  | "other";

export type IssueStatus =
  | "open"
  | "assigned"
  | "in_progress"
  | "resolved"
  | "rejected";

export type PriorityBand = "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";
export type SLAState = "within_sla" | "at_risk" | "breached" | "met";

export type CompletionEvidenceStatus =
  | "pending_worker_evidence"
  | "verified"
  | "admin_confirmed"
  | "needs_review"
  | "rejected";

export interface Attachment {
  id: number;
  file_path: string;
  content_type: string | null;
  latitude: number | null;
  longitude: number | null;
  capture_mode: string | null;
  ai_tags: string[];
  ai_confidence: number | null;
  ai_notes: string | null;
  is_verified: boolean;
}

export interface WorkReview {
  id: number;
  complaint_id: number;
  civic_issue_id: number;
  citizen_id: number;
  officer_id: number | null;
  rating: number;
  review: string | null;
  created_at: string;
}

export interface FieldWorkEvidence {
  id: number;
  civic_issue_id: number;
  officer_id: number;
  file_path: string;
  content_type: string | null;
  latitude: number;
  longitude: number;
  note: string | null;
  uploaded_at: string;
  capture_mode: string;
}

export interface CompletionEvidence {
  id: number;
  complaint_id: number;
  civic_issue_id: number;
  citizen_id: number;
  file_path: string;
  content_type: string | null;
  latitude: number;
  longitude: number;
  uploaded_at: string;
  capture_mode: string;
  matched_field_evidence_id: number | null;
  visual_similarity: number | null;
  location_distance_meters: number | null;
  location_score: number | null;
  verification_score: number | null;
  verification_status: CompletionEvidenceStatus;
  verification_note: string | null;
  reviewed_by: string | null;
  reviewed_at: string | null;
}

export interface Complaint {
  id: number;
  complaint_code: string;
  raw_text: string;
  citizen_name: string | null;
  citizen_email: string | null;
  citizen_phone: string | null;
  category: IssueCategory | null;
  category_confidence: number | null;
  category_terms: string[];
  severity_hint: number | null;
  location_text_raw: string | null;
  location_confidence: number | null;
  latitude: number | null;
  longitude: number | null;
  status: string;
  civic_issue_id: number | null;
  created_at: string;
  attachments: Attachment[];
  review: WorkReview | null;
  completion_evidence: CompletionEvidence[];
}

export interface DuplicateInfo {
  is_duplicate: boolean;
  matched_complaint_code: string | null;
  similarity: number | null;
  shared_terms: string[];
  civic_issue_code: string | null;
}

export interface HistoricalContext {
  source: string;
  source_period: string;
  records: number;
  category_records: number;
  category_share_pct: number;
  top_descriptors: string[];
}

export interface ComplaintSubmitResponse {
  complaint: Complaint;
  civic_issue_code: string;
  civic_issue_id: number;
  priority_score: number;
  priority_band: PriorityBand;
  priority_breakdown: PriorityFactor[];
  duplicate_info: DuplicateInfo;
  location_matched: boolean;
  sla_due_at: string | null;
  sla_target_hours: number | null;
  historical_context?: HistoricalContext | null;
  ai_explanation?: string | null;
  input_language?: string | null;
  input_language_name?: string | null;
  language_confidence?: number | null;
  normalized_text?: string | null;
  classification_method?: string | null;
  department?: string | null;
  assigned_to?: string | null;
  assignment_source?: string | null;
  assignment_note?: string | null;
}

export interface PriorityFactor {
  key: string;
  label: string;
  points: number;
  max_points: number;
  explanation: string;
}

export interface StatusHistoryEntry {
  from_status: string | null;
  to_status: string;
  changed_by: string | null;
  note: string | null;
  changed_at: string;
}

export interface SLARecord {
  target_hours: number;
  due_at: string;
  resolved_at: string | null;
  state: SLAState;
}

export interface CivicIssueSummary {
  id: number;
  issue_code: string;
  category: IssueCategory;
  representative_text: string;
  location_text_raw: string | null;
  latitude: number | null;
  longitude: number | null;
  priority_score: number;
  priority_band: PriorityBand;
  status: IssueStatus;
  department: string | null;
  assigned_to: string | null;
  assignment_source: string | null;
  assignment_note: string | null;
  complaint_count: number;
  created_at: string;
  sla_record: SLARecord | null;
}

export interface CivicIssueDetail extends CivicIssueSummary {
  assigned_to: string | null;
  department: string | null;
  updated_at: string;
  resolved_at: string | null;
  priority_breakdown: PriorityFactor[];
  complaints: Complaint[];
  field_work_evidence: FieldWorkEvidence[];
  completion_evidence: CompletionEvidence[];
  status_history: StatusHistoryEntry[];
}

export interface CompletionEvidenceResponse {
  evidence: CompletionEvidence;
  issue_status: IssueStatus;
  admin_confirmation_pending: boolean;
}

export interface DashboardMetrics {
  total_complaints: number;
  total_civic_issues: number;
  open_issues: number;
  critical_issues: number;
  high_issues: number;
  resolved_issues: number;
  duplicates_consolidated: number;
  sla_within: number;
  sla_at_risk: number;
  sla_breached: number;
  sla_compliance_pct: number;
  avg_resolution_hours: number | null;
  by_category: Record<string, number>;
  by_status: Record<string, number>;
}

export interface MapPoint {
  id: number;
  issue_code: string;
  category: IssueCategory;
  latitude: number;
  longitude: number;
  priority_band: PriorityBand;
  priority_score: number;
  status: IssueStatus;
  complaint_count: number;
  location_name: string | null;
}

export const CATEGORY_LABELS: Record<string, string> = {
  pothole: "Pothole",
  garbage: "Garbage",
  streetlight: "Streetlight",
  drainage: "Drainage",
  road_infrastructure: "Road / Infrastructure",
  water_supply: "Water Supply",
  other: "Other",
};

export const PRIORITY_COLORS: Record<PriorityBand, string> = {
  CRITICAL: "#C43E1D",
  HIGH: "#D6541A",
  MEDIUM: "#C99A2E",
  LOW: "#3F7D6B",
};

export const STATUS_LABELS: Record<string, string> = {
  open: "Open",
  assigned: "Assigned",
  in_progress: "In Progress",
  resolved: "Resolved",
  rejected: "Rejected",
  submitted: "Submitted",
  triaged: "Triaged",
  merged: "Merged",
};

export const DEPARTMENT_NAMES = [
  "Pothole Response",
  "Garbage & Waste",
  "Streetlight Maintenance",
  "Drainage Response",
  "Road Infrastructure",
  "Water Supply",
] as const;

export const SERVICE_CATEGORY_ORDER: IssueCategory[] = [
  "pothole",
  "garbage",
  "streetlight",
  "drainage",
  "road_infrastructure",
  "water_supply",
];

export interface WorkerRoster {
  id: number;
  name: string;
  email: string | null;
  role: string;
  service_category: IssueCategory | null;
  department: string | null;
  availability_status: string;
  is_active: boolean;
  active_cases: number;
  queued_cases: number;
  current_issue_codes: string[];
}

export interface WorkerOverview {
  worker: WorkerRoster;
  category: IssueCategory;
  department: string;
  max_active_cases: number;
  category_open_cases: number;
  category_active_cases: number;
  category_resolved_cases: number;
  sibling_workers: WorkerRoster[];
}
