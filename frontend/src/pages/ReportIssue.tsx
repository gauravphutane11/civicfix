import { FormEvent, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import PageFrame from "../components/common/PageFrame";
import { api } from "../api";
import { useAuth } from "../auth";
import type { ComplaintSubmitResponse } from "../types";

const MAX_IMAGE_SIZE = 8 * 1024 * 1024;
const ALLOWED_IMAGE_TYPES = [
  "image/jpeg",
  "image/png",
  "image/webp",
];

function Step({
  n,
  label,
  active,
}: {
  n: string;
  label: string;
  active: boolean;
}) {
  return (
    <div
      className={`flex items-center gap-2 ${
        active ? "text-indigo-700" : "text-slate-400"
      }`}
    >
      <span
        className={`w-7 h-7 rounded-full grid place-items-center text-xs font-bold ${
          active ? "bg-indigo-600 text-white" : "bg-slate-100"
        }`}
      >
        {n}
      </span>
      <span className="text-sm font-semibold">{label}</span>
    </div>
  );
}

export default function ReportIssue() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const fileRef = useRef<HTMLInputElement>(null);

  const [text, setText] = useState("");
  const [image, setImage] = useState<File | null>(null);
  const [preview, setPreview] = useState("");
  const [lat, setLat] = useState<number | undefined>();
  const [lon, setLon] = useState<number | undefined>();
  const [locationMessage, setLocationMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<ComplaintSubmitResponse | null>(null);

  const locationCaptured = lat !== undefined && lon !== undefined;

  const choose = (file: File | null) => {
    setError("");
    setImage(null);
    setPreview("");

    if (!file) return;

    if (!ALLOWED_IMAGE_TYPES.includes(file.type)) {
      setError("Please upload JPG, PNG or WebP.");
      return;
    }

    if (file.size > MAX_IMAGE_SIZE) {
      setError("The image must be 8 MB or smaller.");
      return;
    }

    setImage(file);
    setPreview(URL.createObjectURL(file));
  };

  const locate = () => {
    setError("");

    if (!navigator.geolocation) {
      setLocationMessage("Location is unavailable in this browser.");
      return;
    }

    setLocationMessage("Reading device location…");

    navigator.geolocation.getCurrentPosition(
      (position) => {
        setLat(position.coords.latitude);
        setLon(position.coords.longitude);
        setLocationMessage(
          "Location captured · used for mapping and nearby duplicate detection.",
        );
      },
      () => {
        setLat(undefined);
        setLon(undefined);
        setLocationMessage(
          "Location permission was not granted. Enable location access and try again.",
        );
      },
      {
        enableHighAccuracy: true,
        timeout: 10000,
        maximumAge: 0,
      },
    );
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setError("");

    if (text.trim().length < 8) {
      setError("Please describe the issue in a little more detail.");
      return;
    }

    if (!image) {
      setError("A clear photo of the issue is required.");
      return;
    }

    if (!locationCaptured) {
      setError("Your location is required. Use the location button before submitting.");
      return;
    }

    setBusy(true);

    try {
      const response = await api.submitComplaint({
        raw_text: text,
        latitude: lat,
        longitude: lon,
        image,
      });
      setResult(response);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to submit the report",
      );
    } finally {
      setBusy(false);
    }
  };

  const reset = () => {
    setResult(null);
    setText("");
    setImage(null);
    setPreview("");
    setLat(undefined);
    setLon(undefined);
    setLocationMessage("");
    setError("");
  };

  if (result) {
    const historical = result.historical_context;
    const categoryLabel =
      result.complaint.category?.replaceAll("_", " / ") ?? "Unknown";

    return (
      <PageFrame>
        <section className="civic-shell py-10 md:py-14">
          <div className="max-w-[1080px] mx-auto">
            <div className="flex flex-wrap items-end justify-between gap-4">
              <div>
                <div className="text-xs uppercase tracking-widest text-slate-400">
                  Report received
                </div>
                <h1 className="font-display text-4xl md:text-5xl font-extrabold mt-2">
                  Your civic case is live.
                </h1>
              </div>
              <span className="tag bg-emerald-50 text-emerald-700">
                AI triage complete
              </span>
            </div>

            <div className="grid lg:grid-cols-[1.15fr_.85fr] gap-6 mt-8">
              <div className="card p-7">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <div className="text-xs uppercase tracking-widest text-slate-400">
                      Complaint ID
                    </div>
                    <div className="font-mono text-2xl font-bold mt-1">
                      {result.complaint.complaint_code}
                    </div>
                  </div>
                  <div className="tag bg-indigo-50 text-indigo-700">
                    {result.priority_band} · {result.priority_score}/100
                  </div>
                </div>

                <p className="text-lg leading-8 text-slate-700 mt-7">
                  {result.complaint.raw_text}
                </p>

                {preview && (
                  <img
                    src={preview}
                    alt="Submitted civic evidence"
                    className="mt-6 w-full h-72 object-cover rounded-xl border border-slate-200"
                  />
                )}

                <div className="grid sm:grid-cols-2 gap-4 mt-6">
                  <div className="card-soft p-4">
                    <div className="text-xs text-slate-400 uppercase tracking-widest">
                      AI category
                    </div>
                    <div className="font-semibold mt-2 capitalize">
                      {categoryLabel}
                    </div>
                    <div className="text-sm text-slate-500 mt-1">
                      {Math.round(
                        (result.complaint.category_confidence ?? 0) * 100,
                      )}% confidence
                    </div>
                  </div>

                  <div className="card-soft p-4">
                    <div className="text-xs text-slate-400 uppercase tracking-widest">
                      Civic issue
                    </div>
                    <div className="font-mono font-bold mt-2">
                      {result.civic_issue_code}
                    </div>
                    <div className="text-sm text-slate-500 mt-1">
                      {result.duplicate_info.is_duplicate
                        ? "Linked to a related existing issue"
                        : "New civic case"}
                    </div>
                  </div>
                </div>

                <div className="card-soft p-5 mt-6">
                  <div className="text-xs uppercase tracking-widest text-slate-400">
                    AI explanation
                  </div>
                  <p className="text-sm leading-6 text-slate-600 mt-3">
                    {result.ai_explanation ??
                      "The system classified, mapped and prioritized this report using the CivicFix decision pipeline."}
                  </p>
                </div>

                <div className="grid sm:grid-cols-2 gap-4 mt-4">
                  <div className="card-soft p-5">
                    <div className="text-xs uppercase tracking-widest text-slate-400">
                      Priority transparency
                    </div>
                    <div className="space-y-3 mt-4">
                      {result.priority_breakdown.map((factor) => (
                        <div key={factor.key}>
                          <div className="flex items-center justify-between gap-3 text-xs">
                            <span className="text-slate-500">
                              {factor.label}
                            </span>
                            <span className="font-mono font-semibold">
                              {factor.points}/{factor.max_points}
                            </span>
                          </div>
                          <div className="h-1.5 bg-slate-100 rounded-full mt-1 overflow-hidden">
                            <div
                              className="h-full rounded-full bg-indigo-500"
                              style={{
                                width: `${Math.min(
                                  100,
                                  (factor.points / factor.max_points) * 100,
                                )}%`,
                              }}
                            />
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="card-soft p-5">
                    <div className="text-xs uppercase tracking-widest text-slate-400">
                      Location evidence
                    </div>
                    <div className="font-semibold mt-3">
                      {result.complaint.location_text_raw ??
                        "Mapped coordinates"}
                    </div>
                    <div className="text-sm text-slate-500 mt-1">
                      {result.location_matched
                        ? "Used for civic mapping and duplicate proximity analysis."
                        : "Location recorded but not confidently resolved."}
                    </div>
                    {result.complaint.latitude != null &&
                      result.complaint.longitude != null && (
                        <div className="font-mono text-xs text-slate-400 mt-3">
                          {result.complaint.latitude.toFixed(6)}, {" "}
                          {result.complaint.longitude.toFixed(6)}
                        </div>
                      )}
                  </div>
                </div>

                {result.duplicate_info.is_duplicate && (
                  <div className="card-soft p-5 mt-4">
                    <div className="text-xs uppercase tracking-widest text-slate-400">
                      Duplicate detection
                    </div>
                    <div className="font-semibold mt-3">
                      Linked to {result.duplicate_info.matched_complaint_code}
                    </div>
                    <div className="text-sm text-slate-500 mt-1">
                      Combined similarity: {Math.round(
                        (result.duplicate_info.similarity ?? 0) * 100,
                      )}%
                      {result.duplicate_info.shared_terms.length > 0 &&
                        ` · Shared terms: ${result.duplicate_info.shared_terms.join(", ")}`}
                    </div>
                  </div>
                )}

                {historical && (
                  <div className="card-soft p-5 mt-4">
                    <div className="text-xs uppercase tracking-widest text-slate-400">
                      Historical reference
                    </div>
                    <div className="font-semibold mt-3">
                      {historical.source} · {historical.source_period}
                    </div>
                    <div className="text-sm text-slate-500 mt-1">
                      {historical.records.toLocaleString()} historical records ·{" "}
                      {historical.category_records.toLocaleString()} in this issue category ·{" "}
                      {historical.category_share_pct}% of the sample
                    </div>
                    {historical.top_descriptors.length > 0 && (
                      <div className="flex flex-wrap gap-2 mt-3">
                        {historical.top_descriptors.map((descriptor) => (
                          <span
                            key={descriptor}
                            className="tag bg-white text-slate-600 border border-slate-200"
                          >
                            {descriptor}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>

              <div className="space-y-4">
                <div className="card p-6">
                  <div className="text-xs uppercase tracking-widest text-slate-400">
                    Service clock
                  </div>
                  <div className="font-display text-4xl font-extrabold mt-3">
                    {result.sla_target_hours}h
                  </div>
                  <div className="text-sm text-slate-500 mt-1">
                    target resolution window
                  </div>
                  <div className="mt-5 text-sm text-slate-600">
                    Due {new Date(result.sla_due_at ?? "").toLocaleString()}
                  </div>
                </div>

                <div className="card p-6">
                  <div className="text-xs uppercase tracking-widest text-slate-400">
                    Next step
                  </div>
                  <p className="mt-3 text-slate-600 leading-6">
                    Your report is connected to <strong>{user?.name}</strong>.
                    Check My Complaints anytime for the case status and service
                    clock.
                  </p>
                  <div className="flex flex-wrap gap-3 mt-5">
                    <button
                      onClick={() => navigate("/complaints")}
                      className="btn-primary"
                    >
                      View my complaints
                    </button>
                    <button
                      onClick={reset}
                      className="btn-secondary"
                    >
                      Report another
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>
      </PageFrame>
    );
  }

  return (
    <PageFrame>
      <section className="civic-shell py-10 md:py-14">
        <div className="max-w-[1080px] mx-auto">
          <div className="flex flex-wrap items-end justify-between gap-6">
            <div>
              <div className="text-xs uppercase tracking-[.18em] text-indigo-600 font-bold">
                Citizen report
              </div>
              <h1 className="font-display text-5xl md:text-6xl font-extrabold tracking-[-.05em] mt-3">
                Tell us what needs fixing.
              </h1>
              <p className="text-lg text-slate-500 mt-4 max-w-2xl leading-7">
                Write what happened, add a photo, share your location and let
                CivicFix structure the rest.
              </p>
            </div>

            <div className="hidden sm:flex gap-5">
              <Step n="1" label="Describe" active />
              <Step n="2" label="Evidence" active />
              <Step n="3" label="Triage" active />
            </div>
          </div>

          <form
            onSubmit={submit}
            className="grid lg:grid-cols-[1fr_380px] gap-6 mt-9"
          >
            <div className="card p-7 md:p-8">
              <label className="block">
                <span className="text-sm font-bold">What is wrong?</span>
                <textarea
                  value={text}
                  onChange={(event) => setText(event.target.value)}
                  className="input-ui mt-2 min-h-48 resize-y"
                  placeholder="Example: Large pothole near Gate 2. Bikes are slipping at night and traffic has to move around it."
                  required
                />
              </label>

              <div className="mt-7">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-sm font-bold">Photo evidence</div>
                    <div className="text-xs text-slate-400 mt-1">
                      Required · JPG, PNG or WebP · up to 8 MB
                    </div>
                  </div>
                  <span className="tag bg-amber-50 text-amber-700">
                    Required
                  </span>
                </div>

                <div
                  onClick={() => fileRef.current?.click()}
                  className="mt-3 rounded-2xl border-2 border-dashed border-slate-200 bg-slate-50/70 p-5 cursor-pointer hover:border-indigo-200 hover:bg-indigo-50/40 transition"
                >
                  {preview ? (
                    <img
                      src={preview}
                      alt="Evidence preview"
                      className="w-full h-64 object-cover rounded-xl"
                    />
                  ) : (
                    <div className="h-40 grid place-items-center text-center">
                      <div>
                        <div className="w-12 h-12 rounded-2xl bg-white border border-slate-200 grid place-items-center mx-auto text-indigo-600 text-xl">
                          +
                        </div>
                        <div className="font-semibold mt-3">
                          Choose a clear photo
                        </div>
                        <div className="text-sm text-slate-400 mt-1">
                          A real-world image helps verify the report.
                        </div>
                      </div>
                    </div>
                  )}

                  <input
                    ref={fileRef}
                    type="file"
                    className="hidden"
                    accept="image/png,image/jpeg,image/webp"
                    onChange={(event) =>
                      choose(event.target.files?.[0] ?? null)
                    }
                  />
                </div>

                {image && (
                  <div className="text-xs text-slate-500 mt-2">
                    {image.name}
                  </div>
                )}
              </div>

              <div className="mt-7">
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <div className="text-sm font-bold">
                      Location <span className="text-red-500">Required</span>
                    </div>
                    <div className="text-xs text-slate-400 mt-1">
                      CivicFix uses your coordinates for mapping and nearby duplicate detection.
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={locate}
                    className="btn-secondary !py-2.5 shrink-0"
                  >
                    {locationCaptured ? "Refresh location" : "Use my location"}
                  </button>
                </div>

                <div
                  className={`mt-3 rounded-xl border p-3 text-sm ${
                    locationCaptured
                      ? "border-emerald-100 bg-emerald-50 text-emerald-700"
                      : "border-amber-100 bg-amber-50 text-amber-700"
                  }`}
                >
                  {locationCaptured
                    ? `Location captured · ${lat?.toFixed(6)}, ${lon?.toFixed(6)}`
                    : locationMessage ||
                      "Location is required before this report can be submitted."}
                </div>
              </div>

              {error && (
                <div className="mt-6 rounded-xl bg-red-50 border border-red-100 text-red-700 p-3 text-sm">
                  {error}
                </div>
              )}

              <button
                disabled={
                  busy ||
                  !image ||
                  !locationCaptured ||
                  text.trim().length < 8
                }
                className="btn-primary w-full mt-7 py-3.5"
              >
                {busy ? "Analysing your report…" : "Submit civic report →"}
              </button>
            </div>

            <aside className="space-y-4">
              <div className="card p-6">
                <div className="text-xs uppercase tracking-widest text-slate-400">
                  What CivicFix checks
                </div>
                <div className="space-y-4 mt-5">
                  <div>
                    <div className="font-semibold">Issue type</div>
                    <div className="text-sm text-slate-500 mt-1">
                      Pothole, waste, streetlight, drainage, road, water and more.
                    </div>
                  </div>
                  <div>
                    <div className="font-semibold">Location</div>
                    <div className="text-sm text-slate-500 mt-1">
                      Device coordinates or a recognizable landmark are used as spatial evidence.
                    </div>
                  </div>
                  <div>
                    <div className="font-semibold">Related reports</div>
                    <div className="text-sm text-slate-500 mt-1">
                      Probable duplicates can be consolidated into one case.
                    </div>
                  </div>
                  <div>
                    <div className="font-semibold">Priority</div>
                    <div className="text-sm text-slate-500 mt-1">
                      The score is explained instead of being a black box.
                    </div>
                  </div>
                </div>
              </div>

              <div className="card-soft p-5">
                <div className="text-xs uppercase tracking-widest text-slate-400">
                  Signed in as
                </div>
                <div className="font-semibold mt-2">{user?.name}</div>
                <div className="text-sm text-slate-500 mt-1">
                  {user?.email}
                </div>
              </div>
            </aside>
          </form>
        </div>
      </section>
    </PageFrame>
  );
}
