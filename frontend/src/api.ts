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
      // Keep the HTTP status text when the response is not JSON.
    }
    throw new Error(detail);
  }

  return response.json();
}

export interface SubmitComplaintPayload {
  raw_text: string;
  citizen_name?: string;
  citizen_phone?: string;
  latitude?: number;
  longitude?: number;
  image?: File | null;
}

export const api = {
  register(payload: {
    name: string;
    email: string;
    phone?: string;
    password: string;
  }) {
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

  requestCitizenOtp(payload: {
    phone: string;
    name?: string;
    email?: string;
    language?: string;
  }) {
    return request<CitizenOtpRequestResponse>(
      "/auth/citizen/request-otp",
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
    );
  },

  verifyCitizenOtp(phone: string, otp: string) {
    return request<AuthResponse>(
      "/auth/citizen/verify-otp",
      {
        method: "POST",
        body: JSON.stringify({ phone, otp }),
      },
    );
  },

  getMe() {
    return request<AuthUser>("/auth/me");
  },

  submitComplaint(payload: SubmitComplaintPayload): Promise<ComplaintSubmitResponse> {
    const form = new FormData();
    form.append("raw_text", payload.raw_text);

    if (payload.latitude != null) {
      form.append("latitude", String(payload.latitude));
    }

    if (payload.longitude != null) {
      form.append("longitude", String(payload.longitude));
    }

    if (payload.image) {
      form.append("image", payload.image);
    }

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

  listCivicIssues(params?: {
    q?: string;
    category?: string;
    status?: string;
    priority_band?: string;
    min_score?: number;
  }) {
    const query = new URLSearchParams();

    if (params?.q) query.set("q", params.q);
    if (params?.category) query.set("category", params.category);
    if (params?.status) query.set("status", params.status);
    if (params?.priority_band) {
      query.set("priority_band", params.priority_band);
    }
    if (params?.min_score != null) {
      query.set("min_score", String(params.min_score));
    }

    const qs = query.toString();

    return request<CivicIssueSummary[]>(
      `/civic-issues${qs ? `?${qs}` : ""}`,
    );
  },

  getCivicIssue(id: number) {
    return request<CivicIssueDetail>(`/civic-issues/${id}`);
  },

  updateStatus(
    id: number,
    status: string,
    changedBy: string,
    note?: string,
  ) {
    return request<CivicIssueDetail>(`/civic-issues/${id}/status`, {
      method: "PATCH",
      body: JSON.stringify({
        status,
        changed_by: changedBy,
        note,
      }),
    });
  },

  assignIssue(
    id: number,
    assignedTo: string,
    department: string,
  ) {
    return request<CivicIssueDetail>(`/civic-issues/${id}/assign`, {
      method: "PATCH",
      body: JSON.stringify({
        assigned_to: assignedTo,
        department,
        changed_by: "Admin Console",
      }),
    });
  },

  getMetrics() {
    return request<DashboardMetrics>("/dashboard/metrics");
  },

  getMapPoints() {
    return request<MapPoint[]>("/dashboard/map");
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
