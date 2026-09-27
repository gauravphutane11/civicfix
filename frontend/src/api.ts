import type {
  ComplaintSubmitResponse,
  Complaint,
  CivicIssueSummary,
  CivicIssueDetail,
  DashboardMetrics,
  MapPoint,
  AuthResponse,
  AuthUser,
  CitizenOtpRequestResponse,
  FieldWorkEvidence,
  CompletionEvidenceResponse,
  WorkerRoster,
  WorkerOverview,
} from "./types";

const BASE = (import.meta.env.VITE_API_URL || "/api").replace(/\/$/, "");

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (!(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  const token = localStorage.getItem("civicfix_token");
  if (
    token &&
    path !== "/auth/login" &&
    path !== "/auth/register" &&
    path !== "/auth/citizen/request-otp" &&
    path !== "/auth/citizen/verify-otp"
  ) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${BASE}${path}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail || detail;
    } catch {
      // Keep HTTP status text for non-JSON responses.
    }
    throw new Error(detail);
  }

  return response.json();
}

export interface SubmitComplaintPayload {
  raw_text: string;
  language?: string;
  citizen_name?: string;
  citizen_phone?: string;
  latitude?: number;
  longitude?: number;
  photo_latitude?: number;
  photo_longitude?: number;
  photo_capture_mode?: string;
  image?: File | null;
}

export const api = {
  register(payload: { name: string; email: string; phone?: string; password: string }) {
    return request<AuthResponse>("/auth/register", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  login(email: string, password: string) {
    return request<AuthResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
  },

  requestCitizenOtp(payload: { phone: string; name?: string; email?: string; language?: string }) {
    return request<CitizenOtpRequestResponse>("/auth/citizen/request-otp", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  verifyCitizenOtp(phone: string, otp: string) {
    return request<AuthResponse>("/auth/citizen/verify-otp", {
      method: "POST",
      body: JSON.stringify({ phone, otp }),
    });
  },

  getMe() {
    return request<AuthUser>("/auth/me");
  },

  submitComplaint(payload: SubmitComplaintPayload): Promise<ComplaintSubmitResponse> {
    const form = new FormData();
    form.append("raw_text", payload.raw_text);
    if (payload.language) form.append("language", payload.language);
    if (payload.latitude != null) form.append("latitude", String(payload.latitude));
    if (payload.longitude != null) form.append("longitude", String(payload.longitude));
    if (payload.photo_latitude != null) form.append("photo_latitude", String(payload.photo_latitude));
    if (payload.photo_longitude != null) form.append("photo_longitude", String(payload.photo_longitude));
    if (payload.photo_capture_mode) form.append("photo_capture_mode", payload.photo_capture_mode);
    if (payload.image) form.append("image", payload.image);

    return request<ComplaintSubmitResponse>("/complaints", {
      method: "POST",
      body: form,
    });
  },

  getMyComplaints() {
    return request<Complaint[]>("/complaints/mine");
  },

  getComplaint(code: string) {
    return request<Complaint>(`/complaints/${code}`);
  },

  submitWorkReview(complaintCode: string, rating: number, review?: string) {
    return request<Complaint>(`/complaints/${complaintCode}/review`, {
      method: "POST",
      body: JSON.stringify({ rating, review: review?.trim() || undefined }),
    });
  },

  submitCompletionEvidence(
    complaintCode: string,
    photo: File,
    latitude: number,
    longitude: number,
    note?: string,
  ) {
    const form = new FormData();
    form.append("photo", photo);
    form.append("latitude", String(latitude));
    form.append("longitude", String(longitude));
    form.append("capture_mode", "live_camera");
    if (note?.trim()) form.append("note", note.trim());
    return request<CompletionEvidenceResponse>(
      `/complaints/${complaintCode}/completion-evidence`,
      { method: "POST", body: form },
    );
  },

  listCivicIssues(params?: {
    q?: string;
    category?: string;
    status?: string;
    priority_band?: string;
    min_score?: number;
    department?: string;
  }) {
    const query = new URLSearchParams();
    if (params?.q) query.set("q", params.q);
    if (params?.category) query.set("category", params.category);
    if (params?.status) query.set("status", params.status);
    if (params?.priority_band) query.set("priority_band", params.priority_band);
    if (params?.min_score != null) query.set("min_score", String(params.min_score));
    if (params?.department) query.set("department", params.department);
    const qs = query.toString();
    return request<CivicIssueSummary[]>(`/civic-issues${qs ? `?${qs}` : ""}`);
  },

  getCivicIssue(id: number) {
    return request<CivicIssueDetail>(`/civic-issues/${id}`);
  },

  updateStatus(id: number, status: string, changedBy: string, note?: string) {
    return request<CivicIssueDetail>(`/civic-issues/${id}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status, changed_by: changedBy, note }),
    });
  },

  assignIssue(id: number, assignedTo: string, department: string) {
    return request<CivicIssueDetail>(`/civic-issues/${id}/assign`, {
      method: "PATCH",
      body: JSON.stringify({ assigned_to: assignedTo, department, changed_by: "Admin Console" }),
    });
  },

  decideCompletionEvidence(issueId: number, evidenceId: number, approved: boolean, note?: string) {
    return request<CompletionEvidenceResponse>(
      `/civic-issues/${issueId}/completion-evidence/${evidenceId}/decision`,
      {
        method: "PATCH",
        body: JSON.stringify({ approved, note: note?.trim() || undefined }),
      },
    );
  },

  getMetrics() {
    return request<DashboardMetrics>("/dashboard/metrics");
  },

  getMapPoints() {
    return request<MapPoint[]>("/dashboard/map");
  },

  getFieldOfficerIssues() {
    return request<CivicIssueDetail[]>("/field-officer/issues");
  },

  getFieldOfficerIssue(id: number) {
    return request<CivicIssueDetail>(`/field-officer/issues/${id}`);
  },

  updateFieldOfficerStatus(id: number, status: string, note?: string) {
    return request<CivicIssueDetail>(`/field-officer/issues/${id}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status, changed_by: "Field Officer", note }),
    });
  },

  uploadFieldWorkEvidence(
    id: number,
    photo: File,
    latitude: number,
    longitude: number,
    note?: string,
  ) {
    const form = new FormData();
    form.append("photo", photo);
    form.append("latitude", String(latitude));
    form.append("longitude", String(longitude));
    form.append("capture_mode", "live_camera");
    if (note?.trim()) form.append("note", note.trim());
    return request<FieldWorkEvidence>(`/field-officer/issues/${id}/evidence`, {
      method: "POST",
      body: form,
    });
  },

  getWorkerRoster(category?: string) {
    const query = category ? `?category=${encodeURIComponent(category)}` : "";
    return request<WorkerRoster[]>(`/dashboard/workers${query}`);
  },

  getWorkerSummary() {
    return request<{ max_active_cases_per_worker: number; categories: Array<{ category: string; department: string; workers: number; available: number; busy: number; at_capacity: number; active_cases: number; queued_cases: number }> }>("/dashboard/workers/summary");
  },

  getFieldOfficerOverview() {
    return request<WorkerOverview>("/field-officer/overview");
  },

  claimFieldOfficerIssue(id: number) {
    return request<CivicIssueDetail>(`/field-officer/issues/${id}/claim`, { method: "POST" });
  },

  getSlaSummary() {
    return request<any>("/sla/summary");
  },

  verifyAttachment(id: number, verified = true) {
    return request<{ id: number; is_verified: boolean }>(
      `/complaints/attachments/${id}/verify?verified=${verified}`,
      { method: "PATCH" },
    );
  },
};
