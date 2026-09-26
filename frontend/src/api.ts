import type { ComplaintSubmitResponse, Complaint, CivicIssueSummary, CivicIssueDetail, DashboardMetrics, MapPoint, AuthResponse, AuthUser } from "./types";
const BASE = (import.meta.env.VITE_API_URL || "/api").replace(/\/$/, "");

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (!(options.body instanceof FormData)) headers.set("Content-Type", "application/json");

  const token = localStorage.getItem("civicfix_token");
  if (token && path !== "/auth/login" && path !== "/auth/register") headers.set("Authorization", `Bearer ${token}`);

  const res = await fetch(`${BASE}${path}`, { ...options, headers });
  if (!res.ok) {
    let detail = res.statusText;
    try { const body = await res.json(); detail = body.detail || detail; } catch {}
    throw new Error(detail);
  }
  return res.json();
}

export interface SubmitComplaintPayload { raw_text:string; citizen_name?:string; citizen_phone?:string; latitude?:number; longitude?:number; image?:File|null; }
export const api = {
  register(payload:{name:string;email:string;phone?:string;password:string}) { return request<AuthResponse>("/auth/register", {method:"POST", body:JSON.stringify(payload)}); },
  login(email:string,password:string) { return request<AuthResponse>("/auth/login", {method:"POST", body:JSON.stringify({email,password})}); },
  getMe() { return request<AuthUser>("/auth/me"); },
  submitComplaint(payload:SubmitComplaintPayload):Promise<ComplaintSubmitResponse> {
    const form = new FormData(); form.append("raw_text", payload.raw_text);
    if (payload.latitude != null) form.append("latitude", String(payload.latitude));
    if (payload.longitude != null) form.append("longitude", String(payload.longitude));
    if (payload.image) form.append("image", payload.image);
    return request<ComplaintSubmitResponse>("/complaints", { method:"POST", body:form });
  },
  getMyComplaints(){ return request<Complaint[]>("/complaints/mine"); },
  getComplaint(code:string){ return request<Complaint>(`/complaints/${code}`); },
  listCivicIssues(params?:{q?:string;category?:string;status?:string;priority_band?:string;min_score?:number}) {
    const qs = new URLSearchParams(); if(params?.q)qs.set("q",params.q); if(params?.category)qs.set("category",params.category); if(params?.status)qs.set("status",params.status); if(params?.priority_band)qs.set("priority_band",params.priority_band); if(params?.min_score!=null)qs.set("min_score",String(params.min_score)); const q=qs.toString(); return request<CivicIssueSummary[]>(`/civic-issues${q?`?${q}`:""}`);
  },
  getCivicIssue(id:number){ return request<CivicIssueDetail>(`/civic-issues/${id}`); },
  updateStatus(id:number,status:string,changed_by:string,note?:string){ return request<CivicIssueDetail>(`/civic-issues/${id}/status`, { method:"PATCH", body:JSON.stringify({status,changed_by,note}) }); },
  assignIssue(id:number,assigned_to:string,department:string){ return request<CivicIssueDetail>(`/civic-issues/${id}/assign`, { method:"PATCH", body:JSON.stringify({assigned_to,department,changed_by:"Admin Console"}) }); },
  getMetrics(){ return request<DashboardMetrics>("/dashboard/metrics"); },
  getMapPoints(){ return request<MapPoint[]>("/dashboard/map"); },
  getSlaSummary(){ return request<any>("/sla/summary"); },
  verifyAttachment(id:number, verified=true){ return request<{id:number;is_verified:boolean}>(`/complaints/attachments/${id}/verify?verified=${verified}`, {method:"PATCH"}); },
};
