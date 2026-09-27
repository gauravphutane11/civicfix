import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import PageFrame from "../components/common/PageFrame";
import LivePhotoCapture from "../components/common/LivePhotoCapture";
import { api } from "../api";
import { useLanguage } from "../i18n";
import type { Complaint, CompletionEvidenceStatus } from "../types";

function statusStyle(status: string) {
  if (status === "resolved") return "status-green";
  if (status === "rejected") return "status-red";
  if (status === "in_progress") return "status-blue";
  return "status-amber";
}

function verificationLabel(status: CompletionEvidenceStatus) {
  switch (status) {
    case "verified":
      return "AI matched · Resolution verified";
    case "admin_confirmed":
      return "Admin confirmed · Evidence accepted";
    case "needs_review":
      return "Needs admin review";
    case "pending_worker_evidence":
      return "Waiting for worker completion evidence";
    case "rejected":
      return "Evidence rejected · Case needs review";
    default:
      return status;
  }
}

function verificationStyle(status: CompletionEvidenceStatus) {
  if (status === "verified" || status === "admin_confirmed") return "bg-emerald-50 text-emerald-700 border-emerald-100";
  if (status === "rejected") return "bg-red-50 text-red-700 border-red-100";
  if (status === "needs_review") return "bg-amber-50 text-amber-700 border-amber-100";
  return "bg-slate-50 text-slate-600 border-slate-200";
}

function attachmentUrl(path: string) {
  const name = path.split(/[/\\]/).pop();
  const base = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "");
  return name ? `${base}/uploads/${encodeURIComponent(name)}` : "";
}

export default function MyComplaints() {
  const { t, categoryLabel, statusLabel } = useLanguage();
  const [items, setItems] = useState<Complaint[]>([]);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [ratingDraft, setRatingDraft] = useState<Record<number, number>>({});
  const [reviewDraft, setReviewDraft] = useState<Record<number, string>>({});
  const [busy, setBusy] = useState<Record<number, string>>({});
  const [cameraComplaintId, setCameraComplaintId] = useState<number | null>(null);

  const load = async (showSpinner = false) => {
    if (showSpinner) setLoading(true);
    try {
      setItems(await api.getMyComplaints());
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load complaints");
    } finally {
      if (showSpinner) setLoading(false);
    }
  };

  useEffect(() => {
    void load(true);
  }, []);

  const filtered = useMemo(
    () =>
      items.filter((item) => {
        const matchesFilter =
          filter === "all" ||
          (filter === "active"
            ? item.status !== "resolved" && item.status !== "rejected"
            : item.status === filter);
        const q = query.toLowerCase().trim();
        const matchesQuery = !q ||
          item.complaint_code.toLowerCase().includes(q) ||
          item.raw_text.toLowerCase().includes(q) ||
          (item.location_text_raw ?? "").toLowerCase().includes(q);
        return matchesFilter && matchesQuery;
      }),
    [items, filter, query],
  );

  const active = items.filter((item) => item.status !== "resolved" && item.status !== "rejected").length;
  const resolved = items.filter((item) => item.status === "resolved").length;
  const reviewPending = items.filter((item) => item.status === "resolved" && !item.review).length;

  const submitReview = async (complaint: Complaint) => {
    const rating = ratingDraft[complaint.id] ?? 0;
    if (!rating) {
      setError("Select a star rating before submitting your review.");
      return;
    }
    setBusy((current) => ({ ...current, [complaint.id]: "review" }));
    setError("");
    try {
      await api.submitWorkReview(complaint.complaint_code, rating, reviewDraft[complaint.id]);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to submit your review");
    } finally {
      setBusy((current) => ({ ...current, [complaint.id]: "" }));
    }
  };

  const submitAfterWorkEvidence = async (
    complaint: Complaint,
    result: { file: File; latitude: number; longitude: number },
  ) => {
    setBusy((current) => ({ ...current, [complaint.id]: "evidence" }));
    setError("");
    try {
      await api.submitCompletionEvidence(
        complaint.complaint_code,
        result.file,
        result.latitude,
        result.longitude,
        "Citizen after-work confirmation captured from live camera",
      );
      setCameraComplaintId(null);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to submit after-work evidence");
    } finally {
      setBusy((current) => ({ ...current, [complaint.id]: "" }));
    }
  };

  return (
    <PageFrame>
      <section className="citizen-shell citizen-page-section">
        <div className="page-heading-row">
          <div>
            <div className="section-kicker">{t("complaints.kicker")}</div>
            <h1>{t("complaints.title")}</h1>
            <p>{t("complaints.subtitle")}</p>
          </div>
          <Link to="/report" className="citizen-primary-btn">{t("complaints.another")} →</Link>
        </div>

        <div className="citizen-stats">
          <div><span>{t("complaints.total")}</span><strong>{items.length}</strong></div>
          <div><span>{t("complaints.active")}</span><strong className="text-brand">{active}</strong></div>
          <div><span>{t("complaints.resolved")}</span><strong className="text-green">{resolved}</strong></div>
        </div>

        {reviewPending > 0 && (
          <div className="citizen-alert mb-5" role="status">
            <strong>Completed work is ready for your feedback.</strong> You may rate the service and optionally capture an after-work photo from the live camera.
          </div>
        )}

        <div className="complaint-toolbar">
          <input className="input-ui" value={query} onChange={(event) => setQuery(event.target.value)} placeholder={t("complaints.search")} />
          <div className="filter-tabs">
            {[["all", t("complaints.all")], ["active", t("complaints.activeTab")], ["resolved", t("complaints.resolvedTab")]].map(([value, label]) => (
              <button key={value} type="button" className={filter === value ? "active" : ""} onClick={() => setFilter(value)}>{label}</button>
            ))}
          </div>
        </div>

        {error && <div className="citizen-alert mb-5">{error}</div>}

        {loading ? (
          <div className="citizen-loading">{t("complaints.loading")}</div>
        ) : filtered.length ? (
          <div className="complaint-list">
            {filtered.map((complaint) => {
              const completion = complaint.completion_evidence?.[0];
              const canCapture = complaint.status !== "rejected" && !completion;
              const isCameraOpen = cameraComplaintId === complaint.id;
              return (
                <div key={complaint.id} className="complaint-row block">
                  <Link to={`/track/${complaint.complaint_code}`} className="grid md:grid-cols-[150px_1fr] gap-5">
                    <div className="complaint-code">{complaint.complaint_code}</div>
                    <div className="complaint-content">
                      <div className="complaint-title-row">
                        <h2>{complaint.raw_text}</h2>
                        <span className={`status-pill ${statusStyle(complaint.status)}`}>{statusLabel(complaint.status)}</span>
                      </div>
                      <div className="complaint-meta">
                        <span>{categoryLabel(complaint.category) || t("complaints.pending")}</span>
                        <span>{complaint.location_text_raw ?? t("complaints.locationRecorded")}</span>
                        <span>{new Date(complaint.created_at).toLocaleDateString()}</span>
                      </div>
                      <div className="complaint-bottom">
                        <span>{complaint.attachments?.length ?? 0} live photo{(complaint.attachments?.length ?? 0) === 1 ? "" : "s"}</span>
                        <strong>{t("complaints.open")} →</strong>
                      </div>
                    </div>
                  </Link>

                  <div className="mt-5 pt-5 border-t border-slate-100" onClick={(event) => event.stopPropagation()}>
                    {completion && (
                      <div className={`rounded-2xl border p-4 mb-4 ${verificationStyle(completion.verification_status)}`}>
                        <div className="flex flex-wrap items-center justify-between gap-3">
                          <div>
                            <div className="text-xs uppercase tracking-widest font-bold">Resolution evidence</div>
                            <div className="font-semibold mt-1">{verificationLabel(completion.verification_status)}</div>
                          </div>
                          {completion.verification_score != null && <div className="font-mono font-bold">{Math.round(completion.verification_score * 100)}%</div>}
                        </div>
                        <div className="grid sm:grid-cols-3 gap-3 mt-4 text-xs">
                          <div><span className="block opacity-60">Visual similarity</span><strong>{completion.visual_similarity == null ? "—" : `${Math.round(completion.visual_similarity * 100)}%`}</strong></div>
                          <div><span className="block opacity-60">Location distance</span><strong>{completion.location_distance_meters == null ? "—" : `${Math.round(completion.location_distance_meters)} m`}</strong></div>
                          <div><span className="block opacity-60">Worker evidence</span><strong>{completion.matched_field_evidence_id ? "Matched" : "Waiting"}</strong></div>
                        </div>
                        {completion.verification_note && <p className="text-xs mt-3 opacity-80">{completion.verification_note}</p>}
                        <img src={attachmentUrl(completion.file_path)} alt="Citizen live after-work evidence" className="mt-4 w-full max-h-56 object-cover rounded-xl border border-black/5" />
                      </div>
                    )}

                    {canCapture && (complaint.status === "in_progress" || complaint.status === "resolved") && (
                      <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-4 mb-4">
                        <div className="flex flex-wrap items-start justify-between gap-3">
                          <div>
                            <div className="text-xs uppercase tracking-widest text-slate-500 font-bold">Optional after-work confirmation</div>
                            <p className="text-sm text-slate-500 mt-1">Capture the same location after the work is done. CivicFix compares your fresh camera evidence with the field worker's evidence and GPS.</p>
                          </div>
                          <span className="tag bg-slate-100 text-slate-600">Optional</span>
                        </div>
                        {!isCameraOpen ? (
                          <button type="button" className="citizen-primary-btn mt-3" disabled={busy[complaint.id] === "evidence"} onClick={() => setCameraComplaintId(complaint.id)}>
                            {busy[complaint.id] === "evidence" ? "Submitting…" : "Take after-work photo"}
                          </button>
                        ) : (
                          <div className="mt-3">
                            <LivePhotoCapture
                              label="Take after-work confirmation"
                              hint="Live camera only. File selection is not available."
                              disabled={busy[complaint.id] === "evidence"}
                              onCapture={(result) => submitAfterWorkEvidence(complaint, result)}
                            />
                            <button type="button" className="text-link-button mt-2" onClick={() => setCameraComplaintId(null)} disabled={busy[complaint.id] === "evidence"}>Close camera</button>
                          </div>
                        )}
                      </div>
                    )}

                    {complaint.status === "resolved" && (
                      complaint.review ? (
                        <div className="rounded-2xl bg-emerald-50 border border-emerald-100 p-4">
                          <div className="text-xs uppercase tracking-widest text-emerald-700 font-bold">Your review</div>
                          <div className="mt-2 text-xl tracking-[.2em] text-amber-500" aria-label={`${complaint.review.rating} out of 5 stars`}>
                            {"★".repeat(complaint.review.rating)}<span className="text-slate-200">{"★".repeat(5 - complaint.review.rating)}</span>
                          </div>
                          {complaint.review.review && <p className="text-sm text-slate-600 mt-2">“{complaint.review.review}”</p>}
                        </div>
                      ) : (
                        <div className="rounded-2xl bg-slate-50 border border-slate-200 p-4">
                          <div className="text-xs uppercase tracking-widest text-slate-500 font-bold">Review the completed work</div>
                          <p className="text-sm text-slate-500 mt-1">Rate the service and optionally leave a short comment.</p>
                          <div className="flex items-center gap-1 mt-3" role="radiogroup" aria-label="Rate completed work">
                            {[1, 2, 3, 4, 5].map((value) => {
                              const selected = (ratingDraft[complaint.id] ?? 0) >= value;
                              return <button key={value} type="button" className={`text-2xl leading-none ${selected ? "text-amber-500" : "text-slate-300"} hover:text-amber-500`} aria-label={`${value} star${value === 1 ? "" : "s"}`} onClick={() => setRatingDraft((current) => ({ ...current, [complaint.id]: value }))}>★</button>;
                            })}
                          </div>
                          <textarea className="input-ui mt-3 min-h-20" maxLength={500} value={reviewDraft[complaint.id] ?? ""} onChange={(event) => setReviewDraft((current) => ({ ...current, [complaint.id]: event.target.value }))} placeholder="Optional review of the completed work" />
                          <button type="button" className="citizen-primary-btn mt-3" disabled={busy[complaint.id] === "review"} onClick={() => void submitReview(complaint)}>
                            {busy[complaint.id] === "review" ? "Submitting…" : "Submit review"}
                          </button>
                        </div>
                      )
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="empty-state">
            <div className="empty-icon">✓</div>
            <h2>{t("complaints.none")}</h2>
            <p>{t("complaints.first")}</p>
            <Link to="/report" className="citizen-primary-btn">{t("complaints.another")} →</Link>
          </div>
        )}
      </section>
    </PageFrame>
  );
}
