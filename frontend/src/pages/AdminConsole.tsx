import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import OperationsMap from "../components/map/OperationsMap";
import type { CivicIssueDetail, CivicIssueSummary, CompletionEvidence, DashboardMetrics, MapPoint, WorkerRoster } from "../types";
import { CATEGORY_LABELS, DEPARTMENT_NAMES, SERVICE_CATEGORY_ORDER, STATUS_LABELS } from "../types";

function priorityClass(priority: string) {
  if (priority === "CRITICAL") return "bg-red-50 text-red-700 border-red-100";
  if (priority === "HIGH") return "bg-orange-50 text-orange-700 border-orange-100";
  if (priority === "MEDIUM") return "bg-amber-50 text-amber-700 border-amber-100";
  return "bg-emerald-50 text-emerald-700 border-emerald-100";
}

function availabilityClass(status: string) {
  if (status === "available") return "bg-emerald-50 text-emerald-700 border-emerald-100";
  if (status === "busy") return "bg-amber-50 text-amber-700 border-amber-100";
  if (status === "at_capacity") return "bg-red-50 text-red-700 border-red-100";
  return "bg-slate-100 text-slate-500 border-slate-200";
}

function statusClass(status: string) {
  if (status === "resolved") return "bg-emerald-50 text-emerald-700 border-emerald-100";
  if (status === "in_progress") return "bg-blue-50 text-blue-700 border-blue-100";
  if (status === "assigned") return "bg-violet-50 text-violet-700 border-violet-100";
  if (status === "rejected") return "bg-red-50 text-red-700 border-red-100";
  return "bg-amber-50 text-amber-700 border-amber-100";
}

function attachmentUrl(path: string) {
  const name = path.split(/[/\\]/).pop();
  const base = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "");
  return name ? `${base}/uploads/${encodeURIComponent(name)}` : "";
}

function ageLabel(iso: string) {
  const hours = Math.max(0, (Date.now() - new Date(iso).getTime()) / 3600000);
  if (hours < 1) return `${Math.round(hours * 60)}m`;
  if (hours < 24) return `${Math.round(hours)}h`;
  return `${Math.floor(hours / 24)}d`;
}

function attentionScore(issue: CivicIssueSummary) {
  const sla = issue.sla_record?.state;
  return issue.priority_score + (sla === "breached" ? 35 : sla === "at_risk" ? 20 : 0) + (issue.complaint_count > 1 ? Math.min(20, issue.complaint_count * 3) : 0) + (issue.status === "open" ? 6 : 0);
}

function EvidenceCard({ evidence, worker }: { evidence: CompletionEvidence; worker?: { name: string } }) {
  return (
    <div className="rounded-2xl border border-slate-200 overflow-hidden bg-white">
      <div className="grid md:grid-cols-2">
        <div className="p-3 border-b md:border-b-0 md:border-r border-slate-200">
          <div className="text-[10px] uppercase tracking-widest text-slate-400">Citizen live evidence</div>
          <img src={attachmentUrl(evidence.file_path)} alt="Citizen live after-work evidence" className="mt-2 w-full h-52 object-cover rounded-xl" />
          <div className="font-mono text-xs text-slate-400 mt-2">{evidence.latitude.toFixed(6)}, {evidence.longitude.toFixed(6)}</div>
        </div>
        <div className="p-3">
          <div className="text-[10px] uppercase tracking-widest text-slate-400">Matched worker evidence</div>
          {worker ? <div className="font-semibold text-slate-800 mt-2">{worker.name}</div> : <div className="text-sm text-slate-400 mt-2">Not matched yet</div>}
          <div className="grid grid-cols-3 gap-2 mt-3 text-center text-xs">
            <div className="rounded-xl bg-slate-50 p-2"><div className="text-slate-400">Visual</div><div className="font-mono font-bold mt-1">{evidence.visual_similarity == null ? "—" : `${Math.round(evidence.visual_similarity * 100)}%`}</div></div>
            <div className="rounded-xl bg-slate-50 p-2"><div className="text-slate-400">Distance</div><div className="font-mono font-bold mt-1">{evidence.location_distance_meters == null ? "—" : `${Math.round(evidence.location_distance_meters)}m`}</div></div>
            <div className="rounded-xl bg-slate-50 p-2"><div className="text-slate-400">Score</div><div className="font-mono font-bold mt-1">{evidence.verification_score == null ? "—" : `${Math.round(evidence.verification_score * 100)}%`}</div></div>
          </div>
          <div className="mt-3 text-xs text-slate-500">Status: <strong>{evidence.verification_status.replaceAll("_", " ")}</strong></div>
          {evidence.verification_note && <p className="text-xs text-slate-500 mt-2">{evidence.verification_note}</p>}
        </div>
      </div>
    </div>
  );
}

export default function AdminConsole() {
  const { user } = useAuth();
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
  const [points, setPoints] = useState<MapPoint[]>([]);
  const [issues, setIssues] = useState<CivicIssueSummary[]>([]);
  const [workers, setWorkers] = useState<WorkerRoster[]>([]);
  const [detail, setDetail] = useState<CivicIssueDetail | null>(null);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("all");
  const [priority, setPriority] = useState("all");
  const [category, setCategory] = useState("all");
  const [department, setDepartment] = useState("all");
  const [sort, setSort] = useState<"attention" | "priority" | "newest">("attention");
  const [view, setView] = useState<"overview" | "cases" | "workers">("overview");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");
  const [officer, setOfficer] = useState("");
  const [evidenceDecisionBusy, setEvidenceDecisionBusy] = useState<number | null>(null);

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const [m, p, i, w] = await Promise.all([
        api.getMetrics(),
        api.getMapPoints(),
        api.listCivicIssues({
          q: query || undefined,
          status: status !== "all" ? status : undefined,
          priority_band: priority !== "all" ? priority : undefined,
          category: category !== "all" ? category : undefined,
          department: department !== "all" ? department : undefined,
        }),
        api.getWorkerRoster(),
      ]);
      setMetrics(m);
      setPoints(p);
      setIssues(i);
      setWorkers(w);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load admin command center");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 180);
    return () => window.clearTimeout(timer);
  }, [query, status, priority, category, department]);

  const ordered = useMemo(() => {
    const result = [...issues];
    if (sort === "attention") result.sort((a, b) => attentionScore(b) - attentionScore(a));
    else if (sort === "priority") result.sort((a, b) => b.priority_score - a.priority_score);
    else result.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
    return result;
  }, [issues, sort]);

  const workerSummary = useMemo(() => {
    return SERVICE_CATEGORY_ORDER.map((categoryKey) => {
      const members = workers.filter((worker) => worker.service_category === categoryKey);
      return {
        category: categoryKey,
        label: CATEGORY_LABELS[categoryKey],
        department: members[0]?.department ?? DEPARTMENT_NAMES[SERVICE_CATEGORY_ORDER.indexOf(categoryKey)],
        members,
        available: members.filter((worker) => worker.availability_status === "available").length,
        busy: members.filter((worker) => worker.availability_status === "busy").length,
        atCapacity: members.filter((worker) => worker.availability_status === "at_capacity").length,
        active: members.reduce((sum, worker) => sum + worker.active_cases, 0),
        queue: members.length ? Math.max(...members.map((worker) => worker.queued_cases)) : 0,
      };
    });
  }, [workers]);

  const selectedPoint = detail ? points.find((point) => point.id === detail.id) : null;
  const nearbyCount = useMemo(() => {
    if (!detail?.latitude || !detail.longitude) return 0;
    const toRad = (value: number) => (value * Math.PI) / 180;
    const lat1 = toRad(detail.latitude);
    let count = 0;
    for (const point of points) {
      const dLat = toRad(point.latitude - detail.latitude);
      const dLon = toRad(point.longitude - detail.longitude);
      const a = Math.sin(dLat / 2) ** 2 + Math.cos(lat1) * Math.cos(toRad(point.latitude)) * Math.sin(dLon / 2) ** 2;
      const distance = 6371000 * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
      if (distance <= 250) count += 1;
    }
    return count;
  }, [detail, points]);

  const matchingWorkers = useMemo(
    () => detail ? workers.filter((worker) => worker.service_category === detail.category) : [],
    [detail, workers],
  );

  useEffect(() => {
    if (!detail) {
      setOfficer("");
      return;
    }
    const current = matchingWorkers.find((worker) => worker.name === detail.assigned_to || worker.email === detail.assigned_to);
    setOfficer(current?.name ?? matchingWorkers[0]?.name ?? "");
  }, [detail, matchingWorkers]);

  const escalation = ordered.filter((issue) => issue.priority_band === "CRITICAL" || issue.sla_record?.state === "breached" || issue.sla_record?.state === "at_risk").slice(0, 6);

  const exportCsv = () => {
    const header = ["Issue ID", "Category", "Department", "Assigned worker", "Priority", "Score", "Status", "Reports", "SLA", "Created"];
    const rows = ordered.map((issue) => [issue.issue_code, CATEGORY_LABELS[issue.category], issue.department ?? "", issue.assigned_to ?? "", issue.priority_band, issue.priority_score, issue.status, issue.complaint_count, issue.sla_record?.state ?? "", new Date(issue.created_at).toISOString()]);
    const csv = [header, ...rows].map((row) => row.map((value) => `"${String(value).replaceAll('"', '""')}"`).join(",")).join("\n");
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "civicfix-cases.csv";
    anchor.click();
    URL.revokeObjectURL(url);
  };

  const openCase = async (id: number) => {
    setError("");
    try {
      setDetail(await api.getCivicIssue(id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to open the case");
    }
  };

  const saveAssignment = async () => {
    if (!detail || !officer) return;
    setBusy(true);
    setError("");
    try {
      await api.assignIssue(detail.id, officer, detail.department ?? "");
      await Promise.all([load(), openCase(detail.id)]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to assign worker");
    } finally {
      setBusy(false);
    }
  };

  const updateStatus = async (nextStatus: string) => {
    if (!detail) return;
    setBusy(true);
    setError("");
    try {
      await api.updateStatus(detail.id, nextStatus, user?.name ?? "Admin Console", note || undefined);
      setNote("");
      await Promise.all([load(), openCase(detail.id)]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to update case status");
    } finally {
      setBusy(false);
    }
  };

  const decideEvidence = async (evidenceId: number, approved: boolean) => {
    if (!detail) return;
    setEvidenceDecisionBusy(evidenceId);
    setError("");
    try {
      await api.decideCompletionEvidence(detail.id, evidenceId, approved, note || undefined);
      setNote("");
      await Promise.all([load(), openCase(detail.id)]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to process evidence decision");
    } finally {
      setEvidenceDecisionBusy(null);
    }
  };

  const issueWorkerById = useMemo(() => {
    const map = new Map<number, WorkerRoster>();
    for (const worker of workers) map.set(worker.id, worker);
    return map;
  }, [workers]);

  return (
    <div className="admin-layout flex min-h-screen">
      <aside className="admin-sidebar hidden md:flex md:w-[245px] shrink-0 flex-col p-4 sticky top-0 h-screen">
        <Link to="/" className="flex items-center gap-3 px-2 py-3"><div className="brand-mark !shadow-none">CF</div><div><div className="font-display font-extrabold text-white">CivicFix</div><div className="text-[10px] text-slate-400">Municipal command center</div></div></Link>
        <div className="text-[10px] uppercase tracking-[.16em] text-slate-500 px-3 mt-7 mb-2">Workspace</div>
        <nav className="space-y-1">
          {([["overview", "Operations overview"], ["cases", "Case intelligence"], ["workers", "Worker network"]] as const).map(([value, label]) => <button key={value} onClick={() => setView(value)} className={`admin-nav w-full text-left px-3 py-2.5 text-sm ${view === value ? "active" : ""}`}>{label}</button>)}
        </nav>
        <div className="mt-auto rounded-2xl bg-white/5 border border-white/10 p-4"><div className="text-[10px] uppercase tracking-widest text-slate-500">Signed in</div><div className="mt-2 text-sm font-semibold text-white truncate">{user?.name}</div><div className="text-xs text-slate-400 mt-1 truncate">{user?.email}</div></div>
      </aside>

      <main className="flex-1 min-w-0">
        <div className="sticky top-0 z-30 bg-white/95 backdrop-blur border-b border-slate-200">
          <div className="max-w-[1550px] mx-auto px-5 md:px-8 py-4">
            <div className="flex flex-wrap gap-3 items-center"><div className="md:hidden font-display font-extrabold text-lg">CivicFix</div><div className="relative flex-1 min-w-[250px]"><input className="input-ui !rounded-xl" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search issue ID, complaint, citizen, phone or location…" /></div><button onClick={exportCsv} className="btn-secondary !py-2.5">Export CSV</button><Link to="/" className="text-sm font-semibold text-slate-500 hover:text-slate-800">Exit</Link></div>
            <div className="flex flex-wrap gap-2 mt-3"><select value={status} onChange={(event) => setStatus(event.target.value)} className="input-ui !w-auto !py-2 text-sm"><option value="all">All statuses</option><option value="open">Open / queue</option><option value="assigned">Assigned</option><option value="in_progress">In progress</option><option value="resolved">Resolved</option><option value="rejected">Rejected</option></select><select value={priority} onChange={(event) => setPriority(event.target.value)} className="input-ui !w-auto !py-2 text-sm"><option value="all">All priority</option><option value="CRITICAL">Critical</option><option value="HIGH">High</option><option value="MEDIUM">Medium</option><option value="LOW">Low</option></select><select value={category} onChange={(event) => setCategory(event.target.value)} className="input-ui !w-auto !py-2 text-sm"><option value="all">All categories</option>{Object.entries(CATEGORY_LABELS).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select><select value={department} onChange={(event) => setDepartment(event.target.value)} className="input-ui !w-auto !py-2 text-sm"><option value="all">All service units</option>{DEPARTMENT_NAMES.map((name) => <option key={name} value={name}>{name}</option>)}</select><select value={sort} onChange={(event) => setSort(event.target.value as typeof sort)} className="input-ui !w-auto !py-2 text-sm"><option value="attention">Attention first</option><option value="priority">Priority first</option><option value="newest">Newest first</option></select></div>
          </div>
        </div>

        <div className="max-w-[1550px] mx-auto px-5 md:px-8 py-7">
          {error && <div className="citizen-alert mb-5">{error}</div>}

          {view === "overview" && <>
            <section className="grid md:grid-cols-2 xl:grid-cols-5 gap-3">
              <div className="card p-4"><div className="text-[10px] uppercase tracking-widest text-slate-400">Citizen reports</div><div className="font-display text-3xl font-extrabold mt-1">{metrics?.total_complaints ?? "—"}</div></div>
              <div className="card p-4"><div className="text-[10px] uppercase tracking-widest text-slate-400">Civic issues</div><div className="font-display text-3xl font-extrabold mt-1">{metrics?.total_civic_issues ?? "—"}</div></div>
              <div className="card p-4"><div className="text-[10px] uppercase tracking-widest text-slate-400">Critical</div><div className="font-display text-3xl font-extrabold text-red-700 mt-1">{metrics?.critical_issues ?? "—"}</div></div>
              <div className="card p-4"><div className="text-[10px] uppercase tracking-widest text-slate-400">Resolved</div><div className="font-display text-3xl font-extrabold text-emerald-700 mt-1">{metrics?.resolved_issues ?? "—"}</div></div>
              <div className="card p-4"><div className="text-[10px] uppercase tracking-widest text-slate-400">SLA compliance</div><div className="font-display text-3xl font-extrabold mt-1">{metrics ? `${metrics.sla_compliance_pct}%` : "—"}</div></div>
            </section>

            <section className="mt-6">
              <div className="flex flex-wrap items-end justify-between gap-3"><div><div className="text-[11px] uppercase tracking-[.2em] text-indigo-600 font-bold">Live auto-routing</div><h1 className="font-display text-3xl md:text-4xl font-extrabold tracking-[-.035em] mt-1">Six service lanes, two workers each.</h1><p className="text-sm text-slate-500 mt-2">AI classifies every new complaint, then CivicFix chooses an active worker from the matching category. Full workers create a visible queue instead of cross-category assignment.</p></div><button className="btn-secondary !py-2" onClick={() => void load()}>Refresh network</button></div>
              <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-4 mt-4">
                {workerSummary.map((summary) => <button key={summary.category} type="button" onClick={() => { setCategory(summary.category); setView("workers"); }} className="text-left card p-4 hover:border-indigo-200 hover:shadow-md transition"><div className="flex items-start justify-between gap-3"><div><div className="text-[10px] uppercase tracking-widest text-slate-400">{summary.department}</div><div className="font-display text-xl font-bold mt-1">{summary.label}</div></div><span className="tag bg-indigo-50 text-indigo-700 border border-indigo-100">{summary.members.length} workers</span></div><div className="grid grid-cols-4 gap-2 mt-4 text-center"><div className="rounded-xl bg-emerald-50 p-2"><div className="text-[10px] uppercase text-emerald-700">Free</div><div className="font-mono font-bold">{summary.available}</div></div><div className="rounded-xl bg-amber-50 p-2"><div className="text-[10px] uppercase text-amber-700">Busy</div><div className="font-mono font-bold">{summary.busy}</div></div><div className="rounded-xl bg-red-50 p-2"><div className="text-[10px] uppercase text-red-700">Full</div><div className="font-mono font-bold">{summary.atCapacity}</div></div><div className="rounded-xl bg-slate-50 p-2"><div className="text-[10px] uppercase text-slate-500">Queue</div><div className="font-mono font-bold">{summary.queue}</div></div></div><div className="text-xs text-slate-500 mt-3">{summary.active} active case{summary.active === 1 ? "" : "s"} across this lane</div></button>)}
              </div>
            </section>

            <section className="grid xl:grid-cols-[1.1fr_.9fr] gap-5 mt-6">
              <div className="card overflow-hidden"><div className="p-5 border-b border-slate-200"><div className="text-[11px] uppercase tracking-widest text-slate-400">Attention queue</div><div className="font-display text-2xl font-bold mt-1">Cases needing municipal attention</div></div><div className="divide-y divide-slate-100">{escalation.length ? escalation.map((issue) => <button key={issue.id} type="button" onClick={() => void openCase(issue.id)} className="w-full text-left p-4 hover:bg-slate-50"><div className="flex items-start justify-between gap-3"><div><div className="font-mono text-xs text-slate-500">{issue.issue_code}</div><div className="font-semibold mt-1">{issue.representative_text}</div><div className="text-xs text-slate-500 mt-2">{CATEGORY_LABELS[issue.category]} · {issue.assigned_to ?? "Awaiting worker"}</div></div><span className={`tag border ${priorityClass(issue.priority_band)}`}>{issue.priority_band} · {issue.priority_score}</span></div><div className="flex items-center justify-between mt-3 text-xs"><span className="text-slate-400">{ageLabel(issue.created_at)} old · {issue.complaint_count} report{issue.complaint_count === 1 ? "" : "s"}</span><span className={`tag border ${statusClass(issue.status)}`}>{STATUS_LABELS[issue.status]}</span></div></button>) : <div className="p-6 text-sm text-slate-400">No critical or at-risk cases in the current filter.</div>}</div></div>
              <div className="card overflow-hidden"><div className="p-5 border-b border-slate-200"><div className="text-[11px] uppercase tracking-widest text-slate-400">Operations map</div><div className="font-display text-2xl font-bold mt-1">Where reports are happening</div></div><div className="h-[480px]"><OperationsMap points={points} selectedId={detail?.id ?? null} onSelect={(id) => void openCase(id)} /></div></div>
            </section>
          </>}

          {view === "cases" && <section className="card overflow-hidden"><div className="p-5 border-b border-slate-200 flex flex-wrap items-end justify-between gap-3"><div><div className="text-[11px] uppercase tracking-widest text-slate-400">Case intelligence</div><h1 className="font-display text-3xl font-extrabold mt-1">Operational case queue</h1><p className="text-sm text-slate-500 mt-2">Open any case to inspect AI classification, assignment, evidence, SLA and the accountability trail.</p></div><div className="text-sm text-slate-400">{ordered.length} cases</div></div>{loading ? <div className="p-8 text-sm text-slate-400">Loading cases…</div> : ordered.length ? <div className="divide-y divide-slate-100">{ordered.map((issue) => <button key={issue.id} type="button" onClick={() => void openCase(issue.id)} className="w-full text-left p-4 hover:bg-slate-50"><div className="flex flex-wrap items-start justify-between gap-3"><div className="min-w-0"><div className="font-mono text-xs font-bold text-slate-500">{issue.issue_code}</div><div className="font-semibold text-slate-800 mt-1">{issue.representative_text}</div><div className="text-xs text-slate-500 mt-2">{CATEGORY_LABELS[issue.category]} · {issue.location_text_raw ?? "Mapped location"}</div></div><div className="flex items-center gap-2"><span className={`tag border ${priorityClass(issue.priority_band)}`}>{issue.priority_band} · {issue.priority_score}</span><span className={`tag border ${statusClass(issue.status)}`}>{STATUS_LABELS[issue.status]}</span></div></div><div className="flex flex-wrap gap-4 text-xs text-slate-400 mt-3"><span>{issue.complaint_count} citizen report{issue.complaint_count === 1 ? "" : "s"}</span><span>{issue.assigned_to ? `Worker: ${issue.assigned_to}` : "Worker: category queue"}</span><span>{issue.department ?? "No service unit"}</span><span>SLA: {issue.sla_record?.state ?? "—"}</span><span>{ageLabel(issue.created_at)} old</span></div></button>)}</div> : <div className="p-8 text-sm text-slate-400">No cases match the current filters.</div>}</section>}

          {view === "workers" && <section><div className="flex flex-wrap items-end justify-between gap-3"><div><div className="text-[11px] uppercase tracking-[.2em] text-indigo-600 font-bold">Worker network</div><h1 className="font-display text-3xl md:text-4xl font-extrabold mt-1">Provisioned service workers</h1><p className="text-sm text-slate-500 mt-2">Each service category has exactly two active worker accounts. Workers only see their own assigned cases and their category's unassigned queue.</p></div></div><div className="grid md:grid-cols-2 gap-4 mt-5">{workerSummary.map((summary) => <div key={summary.category} className={`card p-5 ${category === summary.category ? "border-indigo-300 ring-2 ring-indigo-50" : ""}`}><div className="flex items-start justify-between gap-3"><div><div className="text-[10px] uppercase tracking-widest text-slate-400">{summary.department}</div><h2 className="font-display text-2xl font-bold mt-1">{summary.label}</h2></div><span className="tag bg-slate-100 text-slate-600">{summary.queue} queued</span></div><div className="space-y-3 mt-5">{summary.members.map((worker) => <div key={worker.id} className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4"><div className="flex items-start justify-between gap-3"><div><div className="font-semibold text-slate-800">{worker.name}</div><div className="text-xs text-slate-500 mt-1">{worker.email}</div></div><span className={`rounded-full border px-2.5 py-1 text-[11px] font-semibold ${availabilityClass(worker.availability_status)}`}>{worker.availability_status.replaceAll("_", " ")}</span></div><div className="grid grid-cols-3 gap-2 mt-3 text-center text-xs"><div className="rounded-xl bg-white border border-slate-200 p-2"><div className="text-slate-400">Active</div><div className="font-mono font-bold mt-1">{worker.active_cases}</div></div><div className="rounded-xl bg-white border border-slate-200 p-2"><div className="text-slate-400">Queue</div><div className="font-mono font-bold mt-1">{worker.queued_cases}</div></div><div className="rounded-xl bg-white border border-slate-200 p-2"><div className="text-slate-400">Capacity</div><div className="font-mono font-bold mt-1">3</div></div></div>{worker.current_issue_codes.length > 0 && <div className="flex flex-wrap gap-1.5 mt-3">{worker.current_issue_codes.map((code) => <span key={code} className="tag bg-white text-slate-600 border border-slate-200">{code}</span>)}</div>}</div>)}</div></div>)}</div></section>}
        </div>

        {detail && <div className="fixed inset-0 z-[5000] bg-slate-950/30 backdrop-blur-[1px] p-3 md:p-6 overflow-y-auto" onClick={() => setDetail(null)}><div className="max-w-[1150px] mx-auto bg-white rounded-[28px] shadow-2xl border border-slate-200 overflow-hidden" onClick={(event) => event.stopPropagation()}><div className="p-5 md:p-7 border-b border-slate-200"><div className="flex flex-wrap items-start justify-between gap-4"><div><div className="flex flex-wrap items-center gap-2"><span className="font-mono text-sm font-bold text-slate-500">{detail.issue_code}</span><span className={`tag border ${priorityClass(detail.priority_band)}`}>{detail.priority_band} · {detail.priority_score}</span><span className={`tag border ${statusClass(detail.status)}`}>{STATUS_LABELS[detail.status]}</span>{detail.assignment_source && <span className="tag bg-indigo-50 text-indigo-700 border border-indigo-100">{detail.assignment_source}</span>}</div><h2 className="font-display text-3xl font-extrabold mt-3">{detail.representative_text}</h2><p className="text-sm text-slate-500 mt-2">{CATEGORY_LABELS[detail.category]} · {detail.department ?? "No department"} · {detail.complaint_count} citizen report{detail.complaint_count === 1 ? "" : "s"}</p></div><button className="btn-secondary" onClick={() => setDetail(null)}>Close</button></div></div>

          <div className="p-5 md:p-7 space-y-5">
            <div className="grid md:grid-cols-4 gap-3"><div className="card-soft p-4"><div className="text-[10px] uppercase tracking-widest text-slate-400">Assigned worker</div><div className="font-semibold mt-1">{detail.assigned_to ?? "Category queue"}</div><div className="text-xs text-slate-500 mt-1">{detail.assignment_note ?? "AI router decides from live capacity."}</div></div><div className="card-soft p-4"><div className="text-[10px] uppercase tracking-widest text-slate-400">SLA</div><div className="font-semibold mt-1">{detail.sla_record?.state ?? "—"}</div><div className="text-xs text-slate-500 mt-1">Due {detail.sla_record?.due_at ? new Date(detail.sla_record.due_at).toLocaleString() : "—"}</div></div><div className="card-soft p-4"><div className="text-[10px] uppercase tracking-widest text-slate-400">250 m zone</div><div className="font-semibold mt-1">{nearbyCount} mapped cases</div><div className="text-xs text-slate-500 mt-1">Geographic context only</div></div><div className="card-soft p-4"><div className="text-[10px] uppercase tracking-widest text-slate-400">Created</div><div className="font-semibold mt-1">{new Date(detail.created_at).toLocaleString()}</div><div className="text-xs text-slate-500 mt-1">{ageLabel(detail.created_at)} old</div></div></div>

            <div className="grid lg:grid-cols-[1.05fr_.95fr] gap-5"><div className="card p-5"><div className="text-[11px] uppercase tracking-widest text-slate-400">Citizen reports</div><div className="space-y-3 mt-4">{detail.complaints.map((complaint) => <div key={complaint.id} className="rounded-2xl bg-slate-50 p-4"><div className="flex flex-wrap items-center justify-between gap-2"><span className="font-mono text-xs font-bold">{complaint.complaint_code}</span><span className="text-xs text-slate-400">{new Date(complaint.created_at).toLocaleString()}</span></div><p className="text-sm text-slate-700 mt-2">{complaint.raw_text}</p><div className="text-xs text-slate-500 mt-2">Citizen: {complaint.citizen_name ?? "Unknown"}</div>{complaint.attachments.map((attachment) => <img key={attachment.id} src={attachmentUrl(attachment.file_path)} alt="Citizen live complaint evidence" className="mt-3 w-full max-h-72 object-cover rounded-xl" />)}</div>)}</div></div><div className="card p-5"><div className="text-[11px] uppercase tracking-widest text-slate-400">Location</div><div className="font-semibold mt-2">{detail.location_text_raw ?? "Mapped coordinates"}</div>{detail.latitude != null && detail.longitude != null && <><div className="font-mono text-xs text-slate-500 mt-2">{detail.latitude.toFixed(6)}, {detail.longitude.toFixed(6)}</div><a className="btn-secondary inline-flex mt-4" target="_blank" rel="noreferrer" href={`https://www.google.com/maps?q=${detail.latitude},${detail.longitude}`}>Open map</a></>}<div className="mt-5 h-72 rounded-2xl overflow-hidden border border-slate-200"><OperationsMap points={points.filter((point) => point.category === detail.category)} selectedId={detail.id} onSelect={(id) => void openCase(id)} /></div><div className="mt-3 text-xs text-slate-400">250 m impact zone is shown on the operations map when the case has coordinates.</div></div></div>

            <div className="card p-5">
              <div className="flex flex-wrap items-end justify-between gap-3">
                <div>
                  <div className="text-[11px] uppercase tracking-widest text-slate-400">Auto-routing</div>
                  <h3 className="font-display text-2xl font-bold mt-1">Matching worker pool</h3>
                  <p className="text-sm text-slate-500 mt-1">Only the two workers provisioned for {CATEGORY_LABELS[detail.category]} can receive this case.</p>
                </div>
                {matchingWorkers.length === 0 && <span className="tag bg-red-50 text-red-700">No worker provisioned</span>}
              </div>
              <div className="grid md:grid-cols-2 gap-3 mt-4">
                {matchingWorkers.map((worker) => (
                  <label
                    key={worker.id}
                    className={`rounded-2xl border p-4 cursor-pointer ${officer === worker.name ? "border-indigo-300 bg-indigo-50/50" : "border-slate-200 bg-white"}`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <input
                          type="radio"
                          name="worker"
                          value={worker.name}
                          checked={officer === worker.name}
                          onChange={() => setOfficer(worker.name)}
                          className="mr-2"
                        />
                        {worker.name}
                      </div>
                      <span className={`tag border ${availabilityClass(worker.availability_status)}`}>
                        {worker.availability_status.replaceAll("_", " ")}
                      </span>
                    </div>
                    <div className="text-xs text-slate-500 mt-2">{worker.active_cases} active · {worker.queued_cases} queued · capacity 3</div>
                    {worker.current_issue_codes.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-2">
                        {worker.current_issue_codes.map((code) => (
                          <span key={code} className="tag bg-slate-50 text-slate-500 border border-slate-200">{code}</span>
                        ))}
                      </div>
                    )}
                  </label>
                ))}
              </div>
              {detail.assigned_to ? (
                <div className="text-xs text-slate-400 mt-3">
                  Current assignment: <strong>{detail.assigned_to}</strong>
                </div>
              ) : (
                <div className="text-xs text-slate-400 mt-3">
                  No worker is currently assigned. The AI router leaves the case queued when both workers are at capacity.
                </div>
              )}
              <button type="button" disabled={!officer || busy} onClick={() => void saveAssignment()} className="btn-primary mt-4">
                {busy ? "Saving…" : "Assign selected worker"}
              </button>
            </div>

            <div className="card p-5"><div className="text-[11px] uppercase tracking-widest text-slate-400">Resolution evidence</div><h3 className="font-display text-2xl font-bold mt-1">Worker + citizen confirmation</h3><p className="text-sm text-slate-500 mt-2">Worker evidence must be captured through the live camera. The citizen can optionally capture a second live photo. CivicFix compares the two images and their capture locations.</p><div className="space-y-4 mt-4">{detail.completion_evidence.length ? detail.completion_evidence.map((evidence) => <div key={evidence.id}><EvidenceCard evidence={evidence} worker={evidence.matched_field_evidence_id ? issueWorkerById.get(evidence.matched_field_evidence_id) : undefined} /><div className="flex flex-wrap gap-2 mt-3">{(evidence.verification_status === "verified" || evidence.verification_status === "needs_review") && <><button type="button" className="btn-primary" disabled={evidenceDecisionBusy === evidence.id} onClick={() => void decideEvidence(evidence.id, true)}>{evidenceDecisionBusy === evidence.id ? "Saving…" : "Confirm completion"}</button><button type="button" className="btn-secondary !border-red-200 !text-red-700 !bg-red-50" disabled={evidenceDecisionBusy === evidence.id} onClick={() => void decideEvidence(evidence.id, false)}>Reject evidence</button></>}</div></div>) : <div className="rounded-2xl border border-dashed border-slate-300 p-5 text-sm text-slate-400">No citizen after-work evidence yet. Worker completion evidence is {detail.field_work_evidence.length ? "available below." : "not submitted yet."}</div>}</div></div>

            {detail.field_work_evidence.length > 0 && <div className="card-soft p-5"><div className="text-[11px] uppercase tracking-widest text-slate-400">Worker live evidence</div><div className="grid md:grid-cols-2 gap-4 mt-4">{detail.field_work_evidence.map((evidence) => <div key={evidence.id} className="rounded-2xl bg-white border border-slate-200 p-3"><img src={attachmentUrl(evidence.file_path)} alt="Worker live completion evidence" className="w-full h-56 object-cover rounded-xl" /><div className="font-mono text-xs text-slate-500 mt-2">{evidence.latitude.toFixed(6)}, {evidence.longitude.toFixed(6)}</div><div className="text-xs text-slate-400 mt-1">{new Date(evidence.uploaded_at).toLocaleString()}</div></div>)}</div></div>}

            <div className="grid lg:grid-cols-2 gap-5"><div className="card p-5"><div className="text-[11px] uppercase tracking-widest text-slate-400">Status controls</div><div className="grid sm:grid-cols-2 gap-2 mt-4">{["open", "assigned", "in_progress", "resolved", "rejected"].filter((next) => next !== detail.status).map((next) => <button key={next} type="button" disabled={busy} onClick={() => void updateStatus(next)} className={`btn-secondary ${next === "resolved" ? "!bg-emerald-50 !border-emerald-200 !text-emerald-700" : ""}`}>{next.replaceAll("_", " ")}</button>)}</div><textarea className="input-ui mt-4 min-h-24" value={note} onChange={(event) => setNote(event.target.value)} placeholder="Optional admin note for the audit timeline" /></div><div className="card p-5"><div className="text-[11px] uppercase tracking-widest text-slate-400">Duplicate cluster</div><div className="font-display text-2xl font-bold mt-1">{detail.complaint_count} report{detail.complaint_count === 1 ? "" : "s"} consolidated</div><div className="space-y-2 mt-4">{detail.complaints.map((complaint) => <div key={complaint.id} className="rounded-xl bg-slate-50 p-3"><div className="flex justify-between text-xs"><span className="font-mono font-bold">{complaint.complaint_code}</span><span className="text-slate-400">{new Date(complaint.created_at).toLocaleDateString()}</span></div><div className="text-sm text-slate-600 mt-2">{complaint.raw_text}</div></div>)}</div></div></div>

            <div className="card p-5"><div className="text-[11px] uppercase tracking-widest text-slate-400">Accountability timeline</div><div className="space-y-4 mt-5">{detail.status_history.map((history, index) => <div key={`${history.changed_at}-${index}`} className="flex gap-3"><div className="w-2 h-2 rounded-full bg-indigo-500 mt-2 shrink-0" /><div><div className="flex flex-wrap gap-2 items-center"><span className="font-semibold">{STATUS_LABELS[history.to_status] ?? history.to_status}</span><span className="text-xs text-slate-400">{new Date(history.changed_at).toLocaleString()}</span></div><div className="text-sm text-slate-500 mt-1">{history.note ?? "Status changed"} · {history.changed_by ?? "System"}</div></div></div>)}</div></div>
          </div>
        </div></div>}
      </main>
    </div>
  );
}
