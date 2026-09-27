import {
  FormEvent,
  useEffect,
  useState,
} from "react";
import {
  Link,
  useNavigate,
  useParams,
} from "react-router-dom";

import PageFrame from "../components/common/PageFrame";
import { api } from "../api";
import { useLanguage } from "../i18n";
import type {
  Complaint,
  CivicIssueDetail,
} from "../types";

function imageUrl(path: string) {
  const name = path
    .split(/[/\\]/)
    .pop();

  const base = (
    import.meta.env.VITE_API_URL || ""
  ).replace(/\/$/, "");

  return name
    ? `${base}/uploads/${encodeURIComponent(name)}`
    : "";
}

function statusStyle(status: string) {
  if (status === "resolved") return "status-green";
  if (status === "rejected") return "status-red";
  return status === "in_progress"
    ? "status-blue"
    : "status-amber";
}

export default function TrackComplaint() {
  const { code } = useParams();
  const navigate = useNavigate();
  const {
    t,
    categoryLabel,
    statusLabel,
  } = useLanguage();

  const [input, setInput] =
    useState(code ?? "");

  const [complaint, setComplaint] =
    useState<Complaint | null>(null);

  const [issue, setIssue] =
    useState<CivicIssueDetail | null>(null);

  const [loading, setLoading] =
    useState(false);

  const [error, setError] =
    useState("");

  const load = async (
    value: string,
  ) => {
    const normalized = value
      .trim()
      .toUpperCase();

    if (!normalized) return;

    setLoading(true);
    setError("");

    try {
      const result =
        await api.getComplaint(
          normalized,
        );

      setComplaint(result);

      setIssue(
        result.civic_issue_id
          ? await api.getCivicIssue(
              result.civic_issue_id,
            )
          : null,
      );

      navigate(
        `/track/${normalized}`,
        { replace: true },
      );
    } catch (err) {
      setComplaint(null);
      setIssue(null);
      setError(
        err instanceof Error
          ? err.message
          : t("track.notFound"),
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (code) {
      setInput(code);
      void load(code);
    }
  }, [code]);

  const submit = (
    event: FormEvent,
  ) => {
    event.preventDefault();
    void load(input);
  };

  return (
    <PageFrame>
      <section className="citizen-shell citizen-page-section">
        <div className="page-heading-row">
          <div>
            <div className="section-kicker">
              {t("track.kicker")}
            </div>

            <h1>
              {t("track.title")}
            </h1>

            <p>
              {t("track.subtitle")}
            </p>
          </div>

          <Link
            to="/complaints"
            className="citizen-outline-btn"
          >
            {t("track.my")}
          </Link>
        </div>

        <form
          onSubmit={submit}
          className="track-search"
        >
          <input
            className="input-ui"
            value={input}
            onChange={(event) =>
              setInput(event.target.value)
            }
            placeholder={t(
              "track.search",
            )}
          />

          <button
            className="citizen-primary-btn"
            type="submit"
            disabled={loading}
          >
            {loading
              ? t("track.opening")
              : t("track.open")}
          </button>
        </form>

        {error && (
          <div className="citizen-alert">
            {error}
          </div>
        )}

        {complaint && (
          <div className="track-grid">
            <div className="citizen-paper-card">
              <div className="track-header">
                <div>
                  <div className="field-caption">
                    {t("track.caseId")}
                  </div>
                  <div className="result-id">
                    {complaint.complaint_code}
                  </div>
                </div>

                <span
                  className={`status-pill ${statusStyle(
                    complaint.status,
                  )}`}
                >
                  {statusLabel(
                    complaint.status,
                  )}
                </span>
              </div>

              <h2 className="track-problem">
                {complaint.raw_text}
              </h2>

              <div className="result-facts">
                <div>
                  <span>
                    {t("track.issueType")}
                  </span>
                  <strong>
                    {categoryLabel(
                      complaint.category,
                    ) || "—"}
                  </strong>
                </div>

                <div>
                  <span>
                    {t("track.location")}
                  </span>
                  <strong>
                    {complaint.location_text_raw ??
                      t(
                        "track.coordinates",
                      )}
                  </strong>
                </div>

                <div>
                  <span>
                    {t("track.submitted")}
                  </span>
                  <strong>
                    {new Date(
                      complaint.created_at,
                    ).toLocaleString()}
                  </strong>
                </div>

                <div>
                  <span>
                    {t("track.civicCase")}
                  </span>
                  <strong>
                    {complaint.civic_issue_id
                      ? `CI-${String(
                          complaint.civic_issue_id,
                        ).padStart(7, "0")}`
                      : "—"}
                  </strong>
                </div>
              </div>

              {complaint.attachments?.length > 0 && (
                <div className="evidence-strip">
                  <div className="section-kicker">
                    {t("track.evidence")}
                  </div>

                  <div className="evidence-grid">
                    {complaint.attachments.map(
                      (attachment) => (
                        <div
                          key={attachment.id}
                          className="evidence-item"
                        >
                          <img
                            src={imageUrl(
                              attachment.file_path,
                            )}
                            alt={t(
                              "track.photoAlt",
                            )}
                          />

                          <div>
                            {attachment.is_verified
                              ? t(
                                  "track.verified",
                                )
                              : t(
                                  "track.submittedEvidence",
                                )}
                          </div>
                        </div>
                      ),
                    )}
                  </div>
                </div>
              )}

              {issue && (
                <div className="citizen-paper-card mt-5 border-slate-200">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <div className="section-kicker">Resolution evidence</div>
                      <h3 className="text-xl font-bold mt-1">Worker + citizen completion check</h3>
                      <p className="text-sm text-slate-500 mt-2">A field officer captures a geotagged completion photo. You can optionally capture a fresh after-work photo from the same place so CivicFix can compare the two.</p>
                    </div>
                    <span className="tag bg-slate-100 text-slate-600">Photo + GPS</span>
                  </div>

                  {issue.completion_evidence.length > 0 ? (
                    <div className="space-y-4 mt-5">
                      {issue.completion_evidence.map((evidence) => {
                        const worker = evidence.matched_field_evidence_id
                          ? issue.field_work_evidence.find((item) => item.id === evidence.matched_field_evidence_id)
                          : undefined;
                        const statusText = evidence.verification_status === "verified"
                          ? "AI matched — resolution verified"
                          : evidence.verification_status === "admin_confirmed"
                          ? "Admin confirmed — evidence accepted"
                          : evidence.verification_status === "needs_review"
                          ? "Needs admin review"
                          : evidence.verification_status === "pending_worker_evidence"
                          ? "Waiting for worker completion photo"
                          : "Evidence rejected";
                        return (
                          <div key={evidence.id} className="rounded-2xl border border-slate-200 overflow-hidden">
                            <div className="px-4 py-3 bg-slate-50 border-b border-slate-200 flex flex-wrap items-center justify-between gap-2">
                              <strong>{statusText}</strong>
                              {evidence.verification_score != null && <span className="font-mono text-sm font-bold">{Math.round(evidence.verification_score * 100)}% match</span>}
                            </div>
                            <div className="grid sm:grid-cols-2 gap-3 p-3">
                              <div>
                                <div className="text-xs font-bold text-slate-600 mb-2">Field officer photo</div>
                                {worker ? <img src={imageUrl(worker.file_path)} alt="Field officer completion" className="w-full h-48 object-cover rounded-xl" /> : <div className="h-48 rounded-xl bg-slate-50 grid place-items-center text-sm text-slate-400">Waiting for worker evidence</div>}
                              </div>
                              <div>
                                <div className="text-xs font-bold text-slate-600 mb-2">Your after-work photo</div>
                                <img src={imageUrl(evidence.file_path)} alt="Citizen after-work" className="w-full h-48 object-cover rounded-xl" />
                              </div>
                            </div>
                            <div className="grid sm:grid-cols-3 gap-3 px-3 pb-3 text-xs text-slate-500">
                              <div><span className="block text-slate-400">Visual similarity</span><strong>{evidence.visual_similarity == null ? "—" : `${Math.round(evidence.visual_similarity * 100)}%`}</strong></div>
                              <div><span className="block text-slate-400">Capture distance</span><strong>{evidence.location_distance_meters == null ? "—" : `${Math.round(evidence.location_distance_meters)} m`}</strong></div>
                              <div><span className="block text-slate-400">Status</span><strong>{evidence.verification_status.replaceAll("_", " ")}</strong></div>
                            </div>
                            {evidence.verification_note && <p className="px-3 pb-4 text-xs text-slate-500">{evidence.verification_note}</p>}
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <div className="mt-4 rounded-xl border border-dashed border-slate-300 p-4 text-sm text-slate-400">No after-work confirmation photo has been submitted for this complaint.</div>
                  )}
                </div>
              )}

              {issue && (
                <div className="timeline-card">
                  <div className="section-kicker">
                    {t("track.timeline")}
                  </div>

                  <div className="timeline">
                    {issue.status_history.map(
                      (history, index) => (
                        <div
                          key={`${history.changed_at}-${index}`}
                          className="timeline-item"
                        >
                          <span />

                          <div>
                            <strong>
                              {statusLabel(
                                history.to_status,
                              )}
                            </strong>

                            <time>
                              {new Date(
                                history.changed_at,
                              ).toLocaleString()}
                            </time>

                            <p>
                              {history.note ??
                                t(
                                  "track.statusChanged",
                                )}
                            </p>
                          </div>
                        </div>
                      ),
                    )}
                  </div>
                </div>
              )}
            </div>

            <aside className="track-side">
              <div className="citizen-paper-card service-card">
                <div className="section-kicker">
                  {t("track.service")}
                </div>

                <div className="service-number">
                  {issue?.sla_record
                    ?.target_hours ??
                    "—"}
                  <span>h</span>
                </div>

                <div className="service-muted">
                  {t("track.target")}
                </div>

                <div className="service-due">
                  {issue?.sla_record
                    ? `${t("track.due")} ${new Date(
                        issue.sla_record.due_at,
                      ).toLocaleString()}`
                    : t("track.notAvailable")}
                </div>
              </div>

              <div className="citizen-paper-card">
                <div className="section-kicker">
                  {t("track.priority")}
                </div>

                <div className="priority-large">
                  {issue?.priority_score ??
                    "—"}
                  <span>/100</span>
                </div>

                <div className="factor-list">
                  {issue?.priority_breakdown.map(
                    (factor) => (
                      <div key={factor.key}>
                        <div>
                          <span>
                            {factor.label}
                          </span>
                          <strong>
                            {factor.points}/
                            {factor.max_points}
                          </strong>
                        </div>
                        <p>
                          {factor.explanation}
                        </p>
                      </div>
                    ),
                  )}
                </div>
              </div>

              <div className="citizen-paper-card">
                <div className="section-kicker">
                  {t("track.next")}
                </div>

                <p className="side-copy">
                  {t("track.nextCopy")}
                </p>

                <Link
                  to="/complaints"
                  className="citizen-outline-btn w-full"
                >
                  {t("track.back")}
                </Link>
              </div>
            </aside>
          </div>
        )}
      </section>
    </PageFrame>
  );
}
