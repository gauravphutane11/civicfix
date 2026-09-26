import {
  FormEvent,
  useEffect,
  useRef,
  useState,
} from "react";
import { useNavigate } from "react-router-dom";

import PageFrame from "../components/common/PageFrame";
import { useAuth } from "../auth";
import { useLanguage, SPEECH_LOCALES } from "../i18n";
import { api } from "../api";
import type {
  ComplaintSubmitResponse,
} from "../types";

const MAX_IMAGE_SIZE = 8 * 1024 * 1024;
const ALLOWED_IMAGE_TYPES = [
  "image/jpeg",
  "image/png",
  "image/webp",
];

type SpeechRecognitionLike = {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  onstart: (() => void) | null;
  onend: (() => void) | null;
  onerror: ((event: any) => void) | null;
  onresult: ((event: any) => void) | null;
  start: () => void;
  stop: () => void;
};

type SpeechRecognitionConstructor = new () => SpeechRecognitionLike;

function speechConstructor(): SpeechRecognitionConstructor | null {
  const browserWindow = window as unknown as {
    SpeechRecognition?: SpeechRecognitionConstructor;
    webkitSpeechRecognition?: SpeechRecognitionConstructor;
  };

  return (
    browserWindow.SpeechRecognition ??
    browserWindow.webkitSpeechRecognition ??
    null
  );
}

function factorLabel(
  key: string,
  fallback: string,
  t: (key: string) => string,
) {
  const labels: Record<string, string> = {
    severity: "priority.severity",
    recurrence: "priority.recurrence",
    location_importance:
      "priority.location",
    age: "priority.age",
    public_impact:
      "priority.publicImpact",
    image_evidence:
      "priority.imageEvidence",
  };

  return labels[key]
    ? t(labels[key])
    : fallback;
}

function Step({
  number,
  title,
  active,
}: {
  number: string;
  title: string;
  active: boolean;
}) {
  return (
    <div
      className={`report-step ${
        active ? "active" : ""
      }`}
    >
      <span>{number}</span>
      <strong>{title}</strong>
    </div>
  );
}

function Result({
  result,
  preview,
  onReset,
}: {
  result: ComplaintSubmitResponse;
  preview: string;
  onReset: () => void;
}) {
  const navigate = useNavigate();
  const {
    t,
    categoryLabel,
  } = useLanguage();

  const historical =
    result.historical_context;

  const category = categoryLabel(
    result.complaint.category,
  ) || "—";

  return (
    <section className="citizen-shell citizen-page-section">
      <div className="result-banner">
        <div>
          <div className="section-kicker">
            {t("result.received")}
          </div>
          <h1>{t("result.title")}</h1>
          <p>{t("result.keep")}</p>
        </div>

        <span className="success-badge">
          {t("result.complete")}
        </span>
      </div>

      <div className="result-grid">
        <div className="citizen-paper-card result-main">
          <div className="result-id-row">
            <div>
              <div className="field-caption">
                {t("result.complaintId")}
              </div>
              <div className="result-id">
                {result.complaint.complaint_code}
              </div>
            </div>

            <div className="priority-pill">
              {result.priority_band} · {result.priority_score}/100
            </div>
          </div>

          <div className="result-quote">
            {result.complaint.raw_text}
          </div>

          {preview && (
            <img
              src={preview}
              alt={t("result.photoAlt")}
              className="result-photo"
            />
          )}

          <div className="result-facts">
            <div>
              <span>{t("result.issueType")}</span>
              <strong>{category}</strong>
              <small>
                {Math.round(
                  (result.complaint.category_confidence ?? 0) * 100,
                )}% {t("result.confidence")}
              </small>
            </div>

            <div>
              <span>{t("result.case")}</span>
              <strong>{result.civic_issue_code}</strong>
              <small>
                {result.duplicate_info.is_duplicate
                  ? t("result.relatedCase")
                  : t("result.newCase")}
              </small>
            </div>

            <div>
              <span>{t("result.location")}</span>
              <strong>
                {result.complaint.location_text_raw ??
                  t("result.coordinates")}
              </strong>
              <small>
                {result.location_matched
                  ? t("result.mapped")
                  : t("result.recorded")}
              </small>
            </div>

            <div>
              <span>{t("result.service")}</span>
              <strong>
                {result.sla_target_hours ?? "—"}h
              </strong>
              <small>
                {t("result.target")}
              </small>
            </div>
          </div>

          <div className="plain-card">
            <div className="section-kicker">
              {t("result.ai")}
            </div>
            <p>
              {result.ai_explanation ??
                t("result.defaultExplanation")}
            </p>
          </div>
        </div>

        <aside className="result-side">
          <div className="citizen-paper-card service-card">
            <div className="section-kicker">
              {t("result.service")}
            </div>
            <div className="service-number">
              {result.sla_target_hours ?? "—"}
              <span>h</span>
            </div>
            <div className="service-muted">
              {t("result.target")}
            </div>
            <div className="service-due">
              {t("result.due")} {" "}
              {result.sla_due_at
                ? new Date(
                    result.sla_due_at,
                  ).toLocaleString()
                : "—"}
            </div>
          </div>

          <div className="citizen-paper-card">
            <div className="section-kicker">
              {t("result.priority")}
            </div>

            <div className="factor-list">
              {result.priority_breakdown.map(
                (factor) => (
                  <div key={factor.key}>
                    <div>
                      <span>
                        {factorLabel(
                          factor.key,
                          factor.label,
                          t,
                        )}
                      </span>
                      <strong>
                        {factor.points}/
                        {factor.max_points}
                      </strong>
                    </div>

                    <div className="factor-track">
                      <i
                        style={{
                          width: `${Math.min(
                            100,
                            (factor.points /
                              factor.max_points) *
                              100,
                          )}%`,
                        }}
                      />
                    </div>
                  </div>
                ),
              )}
            </div>
          </div>

          {historical && (
            <div className="citizen-paper-card">
              <div className="section-kicker">
                {t("result.history")}
              </div>

              <strong className="history-big">
                {historical.category_records.toLocaleString()}
              </strong>

              <div className="service-muted">
                {t("result.historyCopy")} {" "}
                {historical.source_period}.
              </div>

              <div className="history-share">
                {historical.category_share_pct}% · {historical.records.toLocaleString()} {t("result.referenceRecords")}
              </div>
            </div>
          )}

          <div className="citizen-paper-card next-card">
            <div className="section-kicker">
              {t("result.next")}
            </div>

            <ol>
              <li>{t("result.next1")}</li>
              <li>{t("result.next2")}</li>
              <li>{t("result.next3")}</li>
            </ol>

            <div className="result-actions">
              <button
                type="button"
                onClick={() => navigate("/complaints")}
                className="citizen-primary-btn"
              >
                {t("result.view")}
              </button>

              <button
                type="button"
                onClick={onReset}
                className="citizen-outline-btn"
              >
                {t("result.another")}
              </button>
            </div>
          </div>
        </aside>
      </div>
    </section>
  );
}

export default function ReportIssue() {
  const { user } = useAuth();
  const {
    t,
    language,
  } = useLanguage();

  const [text, setText] = useState("");
  const [image, setImage] =
    useState<File | null>(null);
  const [preview, setPreview] =
    useState("");
  const [latitude, setLatitude] =
    useState<number | undefined>();
  const [longitude, setLongitude] =
    useState<number | undefined>();
  const [locationAccuracy, setLocationAccuracy] =
    useState<number | null>(null);

  const [listening, setListening] =
    useState(false);
  const [voiceError, setVoiceError] =
    useState("");

  const [error, setError] =
    useState("");
  const [busy, setBusy] =
    useState(false);

  const [result, setResult] =
    useState<ComplaintSubmitResponse | null>(
      null,
    );

  const recognitionRef =
    useRef<SpeechRecognitionLike | null>(
      null,
    );

  const locationCaptured =
    latitude !== undefined &&
    longitude !== undefined;

  useEffect(() => {
    return () => {
      recognitionRef.current?.stop();
      if (preview) {
        URL.revokeObjectURL(preview);
      }
    };
  }, [preview]);

  const locate = () => {
    setError("");

    if (!navigator.geolocation) {
      setError(
        t("report.locationUnsupported"),
      );
      return;
    }

    navigator.geolocation.getCurrentPosition(
      (position) => {
        setLatitude(
          position.coords.latitude,
        );
        setLongitude(
          position.coords.longitude,
        );
        setLocationAccuracy(
          position.coords.accuracy,
        );
        setError("");
      },
      () => {
        setError(
          t("report.locationPermission"),
        );
      },
      {
        enableHighAccuracy: true,
        timeout: 10000,
        maximumAge: 0,
      },
    );
  };

  const toggleVoice = () => {
    setVoiceError("");

    if (listening) {
      recognitionRef.current?.stop();
      return;
    }

    const Constructor =
      speechConstructor();

    if (!Constructor) {
      setVoiceError(
        t("report.voiceUnsupported"),
      );
      return;
    }

    const recognition =
      new Constructor();

    recognition.lang =
      SPEECH_LOCALES[language];
    recognition.continuous = false;
    recognition.interimResults = false;

    recognition.onstart = () => {
      setListening(true);
      setVoiceError("");
    };

    recognition.onend = () => {
      setListening(false);
      recognitionRef.current = null;
    };

    recognition.onerror = (
      event,
    ) => {
      setListening(false);
      recognitionRef.current = null;

      if (
        event?.error !==
        "aborted"
      ) {
        setVoiceError(
          t("report.voiceFailed"),
        );
      }
    };

    recognition.onresult = (
      event,
    ) => {
      let transcript = "";

      for (
        let index =
          event.resultIndex;
        index <
        event.results.length;
        index += 1
      ) {
        if (
          event.results[index]
            .isFinal
        ) {
          transcript +=
            event.results[index][0]
              .transcript;
        }
      }

      const clean =
        transcript.trim();

      if (clean) {
        setText((previous) =>
          previous.trim()
            ? `${previous.trim()} ${clean}`
            : clean,
        );
      }
    };

    recognitionRef.current =
      recognition;
    recognition.start();
  };

  const handleImage = (
    file: File | undefined,
  ) => {
    setError("");

    if (!file) {
      return;
    }

    if (
      !ALLOWED_IMAGE_TYPES.includes(
        file.type,
      )
    ) {
      setImage(null);
      setPreview("");
      setError(
        t("report.invalidImageType"),
      );
      return;
    }

    if (file.size > MAX_IMAGE_SIZE) {
      setImage(null);
      setPreview("");
      setError(
        t("report.invalidImageSize"),
      );
      return;
    }

    if (preview) {
      URL.revokeObjectURL(preview);
    }

    const nextPreview =
      URL.createObjectURL(file);

    setImage(file);
    setPreview(nextPreview);
  };

  const clearImage = () => {
    if (preview) {
      URL.revokeObjectURL(preview);
    }
    setPreview("");
    setImage(null);
  };

  const submit = async (
    event: FormEvent,
  ) => {
    event.preventDefault();
    setError("");

    if (text.trim().length < 8) {
      setError(
        t("report.descriptionRequired"),
      );
      return;
    }

    if (!image) {
      setError(
        t("report.photoRequired"),
      );
      return;
    }

    if (!locationCaptured) {
      setError(
        t("report.locationRequired"),
      );
      return;
    }

    setBusy(true);

    try {
      const response =
        await api.submitComplaint({
          raw_text: text.trim(),
          citizen_name:
            user?.name,
          citizen_phone:
            user?.phone ?? undefined,
          latitude,
          longitude,
          image,
        });

      setResult(response);
    } catch (err) {
      const message =
        err instanceof Error
          ? err.message
          : "";

      const looksLikeImageRejection = /image|photo|portrait|document|diagram|syllabus|screenshot|civic problem|visual evidence/i.test(
        message,
      );

      setError(
        looksLikeImageRejection
          ? t("report.invalidImage")
          : message || t("report.submitFailed"),
      );
    } finally {
      setBusy(false);
    }
  };

  const reset = () => {
    setResult(null);
    setText("");
    clearImage();
    setError("");
    setVoiceError("");
    setLatitude(undefined);
    setLongitude(undefined);
    setLocationAccuracy(null);
  };

  if (result) {
    return (
      <PageFrame>
        <Result
          result={result}
          preview={preview}
          onReset={reset}
        />
      </PageFrame>
    );
  }

  return (
    <PageFrame>
      <section className="report-page citizen-page-section">
        <div className="citizen-shell">
          <div className="report-header">
            <div>
              <div className="section-kicker">
                {t("report.kicker")}
              </div>

              <h1>
                {t("report.title")}
              </h1>

              <p>
                {t("report.subtitle")}
              </p>
            </div>

            <div className="report-steps">
              <Step
                number="1"
                title={t(
                  "report.describe",
                )}
                active={text.length > 0}
              />
              <Step
                number="2"
                title={t("report.photo")}
                active={Boolean(image)}
              />
              <Step
                number="3"
                title={t("report.location")}
                active={locationCaptured}
              />
            </div>
          </div>

          {error && (
            <div className="citizen-alert">
              {error}
            </div>
          )}

          <form
            onSubmit={submit}
            className="report-layout"
          >
            <div className="citizen-paper-card report-form-card">
              <div className="field-block">
                <label className="field-title">
                  {t("report.problem")}
                </label>

                <textarea
                  value={text}
                  onChange={(event) =>
                    setText(
                      event.target.value,
                    )
                  }
                  className="input-ui report-textarea"
                  placeholder={t(
                    "report.placeholder",
                  )}
                  minLength={8}
                />

                <div className="voice-row">
                  <button
                    type="button"
                    onClick={toggleVoice}
                    className={`voice-button ${
                      listening
                        ? "listening"
                        : ""
                    }`}
                  >
                    <span className="voice-icon">
                      {listening
                        ? "■"
                        : "●"}
                    </span>
                    {listening
                      ? t(
                          "report.stopVoice",
                        )
                      : t(
                          "report.voice",
                        )}
                  </button>

                  <span className="voice-help">
                    {t(
                      "report.voiceHelp",
                    )}
                  </span>
                </div>

                {voiceError && (
                  <div className="field-error">
                    {voiceError}
                  </div>
                )}
              </div>

              <div className="form-divider" />

              <div className="field-block">
                <div className="field-title">
                  {t("report.photo")}
                </div>

                <p className="field-help">
                  {t(
                    "report.photoHelp",
                  )}
                </p>

                <div className="photo-upload-row">
                  <label className="photo-button">
                    {t(
                      "report.choosePhoto",
                    )}
                    <input
                      type="file"
                      accept="image/jpeg,image/png,image/webp"
                      onChange={(event) =>
                        handleImage(
                          event.target.files?.[0],
                        )
                      }
                    />
                  </label>

                  {image && (
                    <button
                      type="button"
                      onClick={clearImage}
                      className="text-link-button"
                    >
                      {t("report.clear")}
                    </button>
                  )}
                </div>

                {preview && (
                  <div className="upload-preview">
                    <img
                      src={preview}
                      alt={t(
                        "report.photoPreview",
                      )}
                    />
                    <div>
                      <strong>
                        {image?.name}
                      </strong>
                      <span>
                        {t(
                          "report.photoChecking",
                        )}
                      </span>
                    </div>
                  </div>
                )}
              </div>

              <div className="form-divider" />

              <div className="field-block">
                <div className="field-title">
                  {t("report.location")}
                </div>

                <p className="field-help">
                  {t(
                    "report.locationHelp",
                  )}
                </p>

                <button
                  type="button"
                  onClick={locate}
                  className={`location-button ${
                    locationCaptured
                      ? "captured"
                      : ""
                  }`}
                >
                  <span>
                    {locationCaptured
                      ? "✓"
                      : "⌖"}
                  </span>
                  {locationCaptured
                    ? t(
                        "report.locationCaptured",
                      )
                    : t(
                        "report.useLocation",
                      )}
                </button>

                {locationCaptured && (
                  <div className="location-readout">
                    <strong>
                      {t(
                        "report.locationCaptured",
                      )}
                    </strong>
                    <span>
                      {latitude?.toFixed(5)}, {" "}
                      {longitude?.toFixed(5)}
                    </span>
                    {locationAccuracy !== null && (
                      <span>
                        ±{Math.round(locationAccuracy)}m
                      </span>
                    )}
                  </div>
                )}
              </div>

              <div className="form-divider" />

              <div className="submit-area">
                <div>
                  <strong>
                    {t("report.before")}
                  </strong>
                  <span>
                    {t("report.clear")}
                  </span>
                </div>

                <button
                  type="submit"
                  disabled={
                    busy ||
                    text.trim().length < 8 ||
                    !image ||
                    !locationCaptured
                  }
                  className="citizen-primary-btn submit-button"
                >
                  {busy
                    ? t(
                        "report.checking",
                      )
                    : t(
                        "report.submit",
                      )}
                </button>
              </div>
            </div>

            <aside className="report-side">
              <div className="citizen-paper-card">
                <div className="section-kicker">
                  {t("report.checks")}
                </div>

                <div className="checks-list">
                  <div>
                    <strong>
                      {t("report.issueType")}
                    </strong>
                    <span>
                      {t(
                        "report.issueTypeCopy",
                      )}
                    </span>
                  </div>

                  <div>
                    <strong>
                      {t(
                        "report.locationEvidence",
                      )}
                    </strong>
                    <span>
                      {t(
                        "report.locationEvidenceCopy",
                      )}
                    </span>
                  </div>

                  <div>
                    <strong>
                      {t(
                        "report.related",
                      )}
                    </strong>
                    <span>
                      {t(
                        "report.relatedCopy",
                      )}
                    </span>
                  </div>

                  <div>
                    <strong>
                      {t(
                        "report.priority",
                      )}
                    </strong>
                    <span>
                      {t(
                        "report.priorityCopy",
                      )}
                    </span>
                  </div>
                </div>
              </div>

              <div className="citizen-paper-card report-note-card">
                <div className="section-kicker">
                  {t("report.photoRule")}
                </div>

                <p>
                  {t(
                    "report.photoRuleCopy",
                  )}
                </p>
              </div>
            </aside>
          </form>
        </div>
      </section>
    </PageFrame>
  );
}
