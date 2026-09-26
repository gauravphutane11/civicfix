import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import PageFrame from "../components/common/PageFrame";
import { api } from "../api";
import { useLanguage } from "../i18n";
import type { Complaint } from "../types";

function statusStyle(status: string) {
  if (status === "resolved") return "status-green";
  if (status === "rejected") return "status-red";
  return status === "in_progress"
    ? "status-blue"
    : "status-amber";
}

export default function MyComplaints() {
  const { t, categoryLabel, statusLabel } = useLanguage();

  const [items, setItems] = useState<Complaint[]>([]);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .getMyComplaints()
      .then(setItems)
      .catch((err) =>
        setError(
          err instanceof Error
            ? err.message
            : "Unable to load complaints",
        ),
      )
      .finally(() => setLoading(false));
  }, []);

  const filtered = useMemo(
    () =>
      items.filter((item) => {
        const matchFilter =
          filter === "all" ||
          (filter === "active"
            ? item.status !== "resolved" &&
              item.status !== "rejected"
            : item.status === filter);

        const q = query
          .toLowerCase()
          .trim();

        const matchQuery =
          !q ||
          item.complaint_code
            .toLowerCase()
            .includes(q) ||
          item.raw_text
            .toLowerCase()
            .includes(q) ||
          (item.location_text_raw ?? "")
            .toLowerCase()
            .includes(q);

        return matchFilter && matchQuery;
      }),
    [items, filter, query],
  );

  const active = items.filter(
    (item) =>
      item.status !== "resolved" &&
      item.status !== "rejected",
  ).length;

  const resolved = items.filter(
    (item) => item.status === "resolved",
  ).length;

  return (
    <PageFrame>
      <section className="citizen-shell citizen-page-section">
        <div className="page-heading-row">
          <div>
            <div className="section-kicker">
              {t("complaints.kicker")}
            </div>

            <h1>
              {t("complaints.title")}
            </h1>

            <p>
              {t("complaints.subtitle")}
            </p>
          </div>

          <Link
            to="/report"
            className="citizen-primary-btn"
          >
            {t("complaints.another")} →
          </Link>
        </div>

        <div className="citizen-stats">
          <div>
            <span>
              {t("complaints.total")}
            </span>
            <strong>{items.length}</strong>
          </div>
          <div>
            <span>
              {t("complaints.active")}
            </span>
            <strong className="text-brand">
              {active}
            </strong>
          </div>
          <div>
            <span>
              {t("complaints.resolved")}
            </span>
            <strong className="text-green">
              {resolved}
            </strong>
          </div>
        </div>

        <div className="complaint-toolbar">
          <input
            className="input-ui"
            value={query}
            onChange={(event) =>
              setQuery(event.target.value)
            }
            placeholder={t(
              "complaints.search",
            )}
          />

          <div className="filter-tabs">
            <button
              type="button"
              className={
                filter === "all"
                  ? "active"
                  : ""
              }
              onClick={() =>
                setFilter("all")
              }
            >
              {t("complaints.all")}
            </button>

            <button
              type="button"
              className={
                filter === "active"
                  ? "active"
                  : ""
              }
              onClick={() =>
                setFilter("active")
              }
            >
              {t("complaints.activeTab")}
            </button>

            <button
              type="button"
              className={
                filter === "resolved"
                  ? "active"
                  : ""
              }
              onClick={() =>
                setFilter("resolved")
              }
            >
              {t("complaints.resolvedTab")}
            </button>
          </div>
        </div>

        {error && (
          <div className="citizen-alert">
            {error}
          </div>
        )}

        {loading ? (
          <div className="citizen-loading">
            {t("complaints.loading")}
          </div>
        ) : filtered.length ? (
          <div className="complaint-list">
            {filtered.map((complaint) => (
              <Link
                key={complaint.id}
                to={`/track/${complaint.complaint_code}`}
                className="complaint-row"
              >
                <div className="complaint-code">
                  {complaint.complaint_code}
                </div>

                <div className="complaint-content">
                  <div className="complaint-title-row">
                    <h2>
                      {complaint.raw_text}
                    </h2>

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

                  <div className="complaint-meta">
                    <span>
                      {categoryLabel(
                        complaint.category,
                      ) ||
                        t("complaints.pending")}
                    </span>

                    <span>
                      {complaint.location_text_raw ??
                        t(
                          "complaints.locationRecorded",
                        )}
                    </span>

                    <span>
                      {new Date(
                        complaint.created_at,
                      ).toLocaleDateString()}
                    </span>
                  </div>

                  <div className="complaint-bottom">
                    <span>
                      {complaint.attachments?.length ?? 0} {t("complaints.photos")}
                    </span>

                    <strong>
                      {t("complaints.open")} →
                    </strong>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        ) : (
          <div className="empty-state">
            <div className="empty-icon">
              ✓
            </div>

            <h2>
              {t("complaints.none")}
            </h2>

            <p>
              {t("complaints.first")}
            </p>

            <Link
              to="/report"
              className="citizen-primary-btn"
            >
              {t("complaints.another")} →
            </Link>
          </div>
        )}
      </section>
    </PageFrame>
  );
}
