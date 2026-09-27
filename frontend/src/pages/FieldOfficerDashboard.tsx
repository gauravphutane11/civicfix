import { useEffect, useMemo, useState } from "react";
import PageFrame from "../components/common/PageFrame";
import LivePhotoCapture from "../components/common/LivePhotoCapture";
import OperationsMap from "../components/map/OperationsMap";
import { api } from "../api";
import { useAuth } from "../auth";
import { CATEGORY_LABELS, STATUS_LABELS, type CivicIssueDetail, type MapPoint, type WorkerOverview } from "../types";

function priorityClass(priority: string) {
  if (priority === "CRITICAL") return "bg-red-50 text-red-700 border-red-100";
  if (priority === "HIGH") return "bg-orange-50 text-orange-700 border-orange-100";
  if (priority === "MEDIUM") return "bg-amber-50 text-amber-700 border-amber-100";
  return "bg-emerald-50 text-emerald-700 border-emerald-100";
}

function statusClass(status: string) {
  if (status === "resolved") return "bg-emerald-50 text-emerald-700 border-emerald-100";
  if (status === "in_progress") return "bg-blue-50 text-blue-700 border-blue-100";
  if (status === "assigned") return "bg-violet-50 text-violet-700 border-violet-100";
  return "bg-amber-50 text-amber-700 border-amber-100";
}

function availabilityClass(status: string) {
  if (status === "available") return "bg-emerald-50 text-emerald-700 border-emerald-100";
  if (status === "at_capacity") return "bg-red-50 text-red-700 border-red-100";
  if (status === "busy") return "bg-amber-50 text-amber-700 border-amber-100";
  return "bg-slate-100 text-slate-500 border-slate-200";
}

function attachmentUrl(path: string) {
  const name = path.split(/[/\\]/).pop();
  const base = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "");
  return name ? `${base}/uploads/${encodeURIComponent(name)}` : "";
}

export default function FieldOfficerDashboard() {
  const { user, logout } = useAuth();
  const [overview, setOverview] = useState<WorkerOverview | null>(null);
  const [issues, setIssues] = useState<CivicIssueDetail[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [filter, setFilter] = useState("all");
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState("");
  const [note, setNote] = useState("");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const [nextOverview, nextIssues] = await Promise.all([
        api.getFieldOfficerOverview(),
        api.getFieldOfficerIssues(),
      ]);
      setOverview(nextOverview);
      setIssues(nextIssues);
      setSelectedId((current) => current ?? nextIssues[0]?.id ?? null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load worker dashboard");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const selected = useMemo(
    () => issues.find((item) => item.id === selectedId) ?? null,
    [issues, selectedId],
  );

  const filtered = useMemo(() => {
    const list = [...issues];
    if (filter !== "all") return list.filter((item) => item.priority_band === filter);
    return list;
  }, [issues, filter]);

  const points = useMemo<MapPoint[]>(
    () =>
      filtered
        .filter((item) => item.latitude != null && item.longitude != null)
        .map((item) => ({
          id: item.id,
          issue_code: item.issue_code,
          category: item.category,
          latitude: item.latitude!,
          longitude: item.longitude!,
          priority_band: item.priority_band,
          priority_score: item.priority_score,
          status: item.status,
          complaint_count: item.complaint_count,
          location_name: item.location_text_raw,
        })),
    [filtered],
  );

  const priorityCounts = useMemo(
    () => ({
      CRITICAL: issues.filter((item) => item.priority_band === "CRITICAL").length,
      HIGH: issues.filter((item) => item.priority_band === "HIGH").length,
      MEDIUM: issues.filter((item) => item.priority_band === "MEDIUM").length,
      LOW: issues.filter((item) => item.priority_band === "LOW").length,
    }),
    [issues],
  );

  const performStatus = async (status: string) => {
    if (!selected) return;
    setWorking(true);
    setError("");
    try {
      await api.updateFieldOfficerStatus(selected.id, status, note || undefined);
      setNote("");
      await load();
      setSelectedId(selected.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to update the case");
    } finally {
      setWorking(false);
    }
  };

  const claim = async () => {
    if (!selected) return;
    setWorking(true);
    setError("");
    try {
      await api.claimFieldOfficerIssue(selected.id);
      await load();
      setSelectedId(selected.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to claim the case");
    } finally {
      setWorking(false);
    }
  };

  return (
    <PageFrame
      navItems={[
        {
          label: "My work queue",
          active: true,
          onClick: () => document.getElementById("worker-queue")?.scrollIntoView({ behavior: "smooth" }),
        },
        {
          label: "Team capacity",
          active: false,
          onClick: () => document.getElementById("team-capacity")?.scrollIntoView({ behavior: "smooth" }),
        },
      ]}
    >
      <main className="citizen-shell citizen-page-section">
        {error && <div className="citizen-alert mb-5">{error}</div>}

        <section className="rounded-[28px] border border-slate-200 bg-white p-5 md:p-7 shadow-sm">
          <div className="flex flex-wrap items-start justify-between gap-5">
            <div>
              <div className="text-[11px] uppercase tracking-[.2em] text-indigo-600 font-bold">Service worker dashboard</div>
              <h1 className="font-display text-3xl md:text-5xl font-extrabold tracking-[-.04em] mt-2">
                {overview?.department ?? user?.department ?? "Service response"}
              </h1>
              <p className="text-slate-500 mt-2 max-w-2xl">
                You only receive cases classified as <strong>{overview ? CATEGORY_LABELS[overview.category] : "your service category"}</strong>. The system routes new complaints automatically and keeps your workload within the configured capacity.
              </p>
            </div>
            <div className="flex items-center gap-3">
              <div className={`rounded-full border px-3 py-2 text-xs font-semibold ${availabilityClass(overview?.worker.availability_status ?? "offline")}`}>
                {overview?.worker.availability_status?.replaceAll("_", " ") ?? "offline"}
              </div>
              <button className="btn-secondary !py-2" onClick={logout}>Sign out</button>
            </div>
          </div>

          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3 mt-7">
            <div className="card-soft p-4"><div className="text-[10px] uppercase tracking-widest text-slate-400">My active cases</div><div className="font-display text-3xl font-extrabold mt-1">{overview?.worker.active_cases ?? 0}</div><div className="text-xs text-slate-500 mt-1">Capacity {overview?.max_active_cases ?? 3}</div></div>
            <div className="card-soft p-4"><div className="text-[10px] uppercase tracking-widest text-slate-400">Category queue</div><div className="font-display text-3xl font-extrabold mt-1">{overview?.worker.queued_cases ?? overview?.category_open_cases ?? 0}</div><div className="text-xs text-slate-500 mt-1">Unassigned cases waiting for a free worker</div></div>
            <div className="card-soft p-4"><div className="text-[10px] uppercase tracking-widest text-slate-400">Category active</div><div className="font-display text-3xl font-extrabold mt-1">{overview?.category_active_cases ?? 0}</div><div className="text-xs text-slate-500 mt-1">Across your two-person service team</div></div>
            <div className="card-soft p-4"><div className="text-[10px] uppercase tracking-widest text-slate-400">Resolved</div><div className="font-display text-3xl font-extrabold text-emerald-700 mt-1">{overview?.category_resolved_cases ?? 0}</div><div className="text-xs text-slate-500 mt-1">Cases completed in your category</div></div>
          </div>
        </section>

        <section id="team-capacity" className="mt-5 rounded-[28px] border border-slate-200 bg-white p-5 md:p-7 shadow-sm">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <div className="text-[11px] uppercase tracking-[.2em] text-indigo-600 font-bold">Team capacity</div>
              <h2 className="font-display text-2xl font-bold mt-1">{overview?.department ?? "Service unit"}</h2>
              <p className="text-sm text-slate-500 mt-1">Two workers are provisioned for this category. CivicFix spreads work across available capacity.</p>
            </div>
            <div className="text-sm text-slate-500">{overview?.worker.current_issue_codes.length ?? 0} active on your account</div>
          </div>
          <div className="grid md:grid-cols-2 gap-3 mt-5">
            {(overview?.sibling_workers ?? []).map((worker) => (
              <div key={worker.id} className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="font-semibold text-slate-800">{worker.name}</div>
                    <div className="text-xs text-slate-500 mt-1">{worker.email}</div>
                  </div>
                  <span className={`rounded-full border px-2.5 py-1 text-[11px] font-semibold ${availabilityClass(worker.availability_status)}`}>
                    {worker.availability_status.replaceAll("_", " ")}
                  </span>
                </div>
                <div className="grid grid-cols-3 gap-2 mt-4 text-center">
                  <div className="rounded-xl bg-white border border-slate-200 p-2"><div className="text-[10px] uppercase text-slate-400">Active</div><div className="font-mono font-bold mt-1">{worker.active_cases}</div></div>
                  <div className="rounded-xl bg-white border border-slate-200 p-2"><div className="text-[10px] uppercase text-slate-400">Queue</div><div className="font-mono font-bold mt-1">{worker.queued_cases}</div></div>
                  <div className="rounded-xl bg-white border border-slate-200 p-2"><div className="text-[10px] uppercase text-slate-400">Capacity</div><div className="font-mono font-bold mt-1">{overview?.max_active_cases ?? 3}</div></div>
                </div>
                {worker.current_issue_codes.length > 0 && <div className="flex flex-wrap gap-1.5 mt-3">{worker.current_issue_codes.map((code) => <span key={code} className="tag bg-white text-slate-600 border border-slate-200">{code}</span>)}</div>}
              </div>
            ))}
          </div>
        </section>

        <div className="flex flex-wrap items-center gap-2 mt-6">
          {(["all", "CRITICAL", "HIGH", "MEDIUM", "LOW"] as const).map((value) => (
            <button key={value} type="button" onClick={() => setFilter(value)} className={`btn-secondary !py-2 ${filter === value ? "!bg-indigo-50 !text-indigo-700 !border-indigo-200" : ""}`}>
              {value === "all" ? "All cases" : value}
            </button>
          ))}
          <button className="btn-secondary !py-2 ml-auto" onClick={() => void load()}>Refresh</button>
        </div>

        <section id="worker-queue" className="grid xl:grid-cols-[1.02fr_.98fr] gap-5 mt-4">
          <div className="rounded-[28px] border border-slate-200 bg-white overflow-hidden shadow-sm">
            <div className="p-5 border-b border-slate-200">
              <div className="text-[11px] uppercase tracking-[.2em] text-slate-500 font-bold">My work queue</div>
              <div className="flex flex-wrap items-end justify-between gap-3 mt-1"><h2 className="font-display text-2xl font-bold">Cases for {overview ? CATEGORY_LABELS[overview.category] : "your category"}</h2><div className="text-sm text-slate-500">{filtered.length} visible</div></div>
              <div className="grid grid-cols-4 gap-2 mt-4 text-center"><div className="rounded-xl bg-red-50 p-2 text-red-700"><div className="text-[10px] uppercase">Critical</div><div className="font-mono font-bold">{priorityCounts.CRITICAL}</div></div><div className="rounded-xl bg-orange-50 p-2 text-orange-700"><div className="text-[10px] uppercase">High</div><div className="font-mono font-bold">{priorityCounts.HIGH}</div></div><div className="rounded-xl bg-amber-50 p-2 text-amber-700"><div className="text-[10px] uppercase">Medium</div><div className="font-mono font-bold">{priorityCounts.MEDIUM}</div></div><div className="rounded-xl bg-emerald-50 p-2 text-emerald-700"><div className="text-[10px] uppercase">Low</div><div className="font-mono font-bold">{priorityCounts.LOW}</div></div></div>
            </div>
            {loading ? <div className="p-8 text-sm text-slate-400">Loading your service queue…</div> : filtered.length === 0 ? <div className="p-8 text-sm text-slate-400">No cases are waiting for this worker account.</div> : <div className="divide-y divide-slate-100">{filtered.map((item) => <button key={item.id} type="button" onClick={() => setSelectedId(item.id)} className={`w-full text-left p-4 hover:bg-slate-50 ${selectedId === item.id ? "bg-indigo-50/60" : ""}`}><div className="flex items-start justify-between gap-3"><div className="min-w-0"><div className="font-mono text-xs font-bold text-slate-500">{item.issue_code}</div><div className="font-semibold text-slate-800 mt-1 line-clamp-2">{item.representative_text}</div><div className="text-xs text-slate-500 mt-2">{item.location_text_raw ?? "Mapped coordinates"}</div></div><span className={`tag shrink-0 border ${priorityClass(item.priority_band)}`}>{item.priority_band} · {item.priority_score}</span></div><div className="flex items-center justify-between gap-3 mt-3 text-xs"><span className="text-slate-400">{item.complaint_count} report{item.complaint_count === 1 ? "" : "s"}</span><span className={`rounded-full border px-2 py-1 ${statusClass(item.status)}`}>{STATUS_LABELS[item.status] ?? item.status}</span></div></button>)}</div>}
          </div>

          <div className="rounded-[28px] border border-slate-200 bg-white overflow-hidden shadow-sm min-h-[620px]">
            <div className="p-4 border-b border-slate-200"><div className="text-[11px] uppercase tracking-[.2em] text-slate-500 font-bold">Ground locations</div><div className="font-display text-xl font-bold mt-1">Category map</div></div>
            <div className="h-[560px]"><OperationsMap points={points} selectedId={selectedId} onSelect={setSelectedId} /></div>
          </div>
        </section>

        {selected && <section className="mt-5 rounded-[28px] border border-slate-200 bg-white p-5 md:p-7 shadow-sm">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <div className="flex flex-wrap items-center gap-2"><span className="font-mono font-bold">{selected.issue_code}</span><span className={`tag border ${priorityClass(selected.priority_band)}`}>{selected.priority_band} · {selected.priority_score}</span><span className={`tag border ${statusClass(selected.status)}`}>{STATUS_LABELS[selected.status] ?? selected.status}</span>{selected.assignment_source && <span className="tag bg-slate-100 text-slate-600">{selected.assignment_source}</span>}</div>
              <h2 className="font-display text-2xl md:text-3xl font-bold mt-3">{selected.representative_text}</h2>
              <p className="text-sm text-slate-500 mt-2">{selected.location_text_raw ?? "Mapped coordinates"} · {selected.complaint_count} citizen report{selected.complaint_count === 1 ? "" : "s"}</p>
            </div>
            <button className="btn-secondary" onClick={() => setSelectedId(null)}>Close</button>
          </div>

          <div className="grid lg:grid-cols-3 gap-4 mt-6">
            <div className="card-soft p-4"><div className="text-[11px] uppercase tracking-widest text-slate-400">Citizen evidence</div>{selected.complaints.map((complaint) => <div key={complaint.id} className="mt-3"><div className="font-mono text-xs font-bold">{complaint.complaint_code}</div><p className="text-sm text-slate-600 mt-2">{complaint.raw_text}</p>{complaint.attachments.map((attachment) => <img key={attachment.id} src={attachmentUrl(attachment.file_path)} className="mt-3 w-full max-h-56 object-cover rounded-2xl" alt="Live citizen evidence" />)}</div>)}</div>
            <div className="card-soft p-4"><div className="text-[11px] uppercase tracking-widest text-slate-400">Case location</div><div className="font-semibold mt-3">{selected.location_text_raw ?? "Mapped coordinates"}</div>{selected.latitude != null && selected.longitude != null && <><div className="font-mono text-xs text-slate-500 mt-2">{selected.latitude.toFixed(6)}, {selected.longitude.toFixed(6)}</div><a className="btn-secondary inline-flex mt-4" target="_blank" rel="noreferrer" href={`https://www.google.com/maps?q=${selected.latitude},${selected.longitude}`}>Open map</a></>}<div className="mt-5 text-xs text-slate-500">SLA: {selected.sla_record?.state ?? "not available"} · due {selected.sla_record?.due_at ? new Date(selected.sla_record.due_at).toLocaleString() : "—"}</div></div>
            <div className="card-soft p-4"><div className="text-[11px] uppercase tracking-widest text-slate-400">Work controls</div><p className="text-sm text-slate-500 mt-3">Start work, then capture a live completion photo from the camera. Resolution is verified from worker and citizen evidence; this dashboard does not allow direct photo-free closure.</p>{selected.assigned_to == null && selected.status === "open" && <button type="button" className="btn-primary mt-4 w-full" disabled={working} onClick={() => void claim()}>{working ? "Claiming…" : "Claim this case"}</button>}{selected.assigned_to != null && selected.status === "assigned" && <button type="button" className="btn-primary mt-4 w-full" disabled={working} onClick={() => void performStatus("in_progress")}>{working ? "Starting…" : "Start work"}</button>}{selected.status === "in_progress" && <div className="mt-4"><LivePhotoCapture label="Capture completion proof" hint="Use the live camera at the work site. CivicFix records the capture location with the evidence." disabled={working} onCapture={async ({ file, latitude, longitude }) => { setWorking(true); setError(""); try { await api.uploadFieldWorkEvidence(selected.id, file, latitude, longitude, note || undefined); setNote(""); await load(); setSelectedId(selected.id); } catch (err) { setError(err instanceof Error ? err.message : "Unable to submit completion evidence"); } finally { setWorking(false); } }} /></div>}{selected.status === "assigned" && <div className="mt-3"><textarea className="input-ui min-h-20" value={note} onChange={(e) => setNote(e.target.value)} placeholder="Optional work note" /></div>}{selected.status === "in_progress" && <div className="mt-3"><textarea className="input-ui min-h-20" value={note} onChange={(e) => setNote(e.target.value)} placeholder="Optional work note" /></div>}</div>
          </div>

          {selected.field_work_evidence.length > 0 && <div className="mt-5"><div className="text-[11px] uppercase tracking-widest text-slate-400">Submitted live completion evidence</div><div className="grid md:grid-cols-2 xl:grid-cols-3 gap-4 mt-3">{selected.field_work_evidence.map((evidence) => <div key={evidence.id} className="rounded-2xl border border-slate-200 p-3"><img src={attachmentUrl(evidence.file_path)} className="w-full h-52 object-cover rounded-xl" alt="Live field completion evidence"/><div className="font-mono text-xs text-slate-500 mt-2">{evidence.latitude.toFixed(6)}, {evidence.longitude.toFixed(6)}</div><div className="text-xs text-slate-500 mt-1">{new Date(evidence.uploaded_at).toLocaleString()}</div>{evidence.note && <div className="text-sm text-slate-600 mt-2">{evidence.note}</div>}</div>)}</div></div>}

          {selected.completion_evidence.length > 0 && <div className="mt-5 rounded-2xl border border-indigo-100 bg-indigo-50/50 p-4"><div className="text-[11px] uppercase tracking-widest text-indigo-600 font-bold">Citizen verification signal</div>{selected.completion_evidence.map((evidence) => <div key={evidence.id} className="mt-3 flex flex-wrap items-center justify-between gap-3"><div><div className="font-semibold text-slate-800">{evidence.verification_status.replaceAll("_", " ")}</div><div className="text-xs text-slate-500 mt-1">{evidence.verification_note ?? "Waiting for both sides of the evidence comparison."}</div></div><div className="text-right"><div className="font-mono font-bold">{evidence.verification_score != null ? `${Math.round(evidence.verification_score * 100)}%` : "—"}</div><div className="text-[10px] uppercase tracking-widest text-slate-400">match score</div></div></div>)}</div>}
        </section>}
      </main>
    </PageFrame>
  );
}
