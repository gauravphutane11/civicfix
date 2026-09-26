import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../api";
import { useAuth } from "../auth";

import OperationsMap from "../components/map/OperationsMap";

import type {
  CivicIssueDetail,
  CivicIssueSummary,
  DashboardMetrics,
  MapPoint,
} from "../types";

import {
  CATEGORY_LABELS,
  STATUS_LABELS,
} from "../types";

/* =========================================================
   HELPERS
   ========================================================= */

function age(iso: string) {
  const hours = Math.max(
    0,
    (Date.now() - new Date(iso).getTime()) / 3600000,
  );

  if (hours < 1) {
    return `${Math.round(hours * 60)}m`;
  }

  if (hours < 24) {
    return `${Math.round(hours)}h`;
  }

  return `${Math.floor(hours / 24)}d`;
}

function attention(
  issue: CivicIssueSummary,
) {
  const sla = issue.sla_record?.state;

  return (
    issue.priority_score +
    (sla === "breached"
      ? 35
      : sla === "at_risk"
        ? 20
        : 0) +
    (issue.complaint_count > 1
      ? Math.min(
          20,
          issue.complaint_count * 3,
        )
      : 0) +
    (issue.status === "open"
      ? 6
      : 0)
  );
}

function slaLabel(
  state?: string | null,
) {
  if (state === "breached") {
    return [
      "Breached",
      "bg-red-50 text-red-700",
    ] as const;
  }

  if (state === "at_risk") {
    return [
      "At risk",
      "bg-amber-50 text-amber-700",
    ] as const;
  }

  if (state === "met") {
    return [
      "Met",
      "bg-emerald-50 text-emerald-700",
    ] as const;
  }

  return [
    "Within SLA",
    "bg-slate-100 text-slate-600",
  ] as const;
}

function priorityClass(
  priority: string,
) {
  return priority === "CRITICAL"
    ? "bg-red-50 text-red-700"
    : priority === "HIGH"
      ? "bg-orange-50 text-orange-700"
      : priority === "MEDIUM"
        ? "bg-amber-50 text-amber-700"
        : "bg-emerald-50 text-emerald-700";
}

function attachmentUrl(
  path: string,
) {
  const name = path
    .split(/[/\\]/)
    .pop();

  const base = (
    import.meta.env.VITE_API_URL || ""
  ).replace(/\/$/, "");

  return name
    ? `${base}/uploads/${encodeURIComponent(
        name,
      )}`
    : "";
}

/* =========================================================
   DISTANCE CALCULATION
   ========================================================= */

function distanceMeters(
  lat1: number,
  lon1: number,
  lat2: number,
  lon2: number,
) {
  const earthRadius = 6_371_000;

  const toRadians = (
    value: number,
  ) => (value * Math.PI) / 180;

  const dLat = toRadians(
    lat2 - lat1,
  );

  const dLon = toRadians(
    lon2 - lon1,
  );

  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRadians(lat1)) *
      Math.cos(toRadians(lat2)) *
      Math.sin(dLon / 2) ** 2;

  const c =
    2 *
    Math.atan2(
      Math.sqrt(a),
      Math.sqrt(1 - a),
    );

  return earthRadius * c;
}

/* =========================================================
   ADMIN CONSOLE
   ========================================================= */

export default function AdminConsole() {
  const { user } = useAuth();

  const [
    view,
    setView,
  ] = useState<
    "overview" | "cases" | "insights"
  >("overview");

  const [
    metrics,
    setMetrics,
  ] =
    useState<DashboardMetrics | null>(
      null,
    );

  const [
    points,
    setPoints,
  ] = useState<MapPoint[]>([]);

  const [
    issues,
    setIssues,
  ] = useState<CivicIssueSummary[]>([]);

  const [
    detail,
    setDetail,
  ] =
    useState<CivicIssueDetail | null>(
      null,
    );

  const [
    query,
    setQuery,
  ] = useState("");

  const [
    status,
    setStatus,
  ] = useState("all");

  const [
    priority,
    setPriority,
  ] = useState("all");

  const [
    category,
    setCategory,
  ] = useState("all");

  const [
    sort,
    setSort,
  ] =
    useState<
      "attention" | "newest" | "priority"
    >("attention");

  const [
    loading,
    setLoading,
  ] = useState(true);

  const [
    error,
    setError,
  ] = useState("");

  /* =======================================================
     LOAD COMMAND CENTER
     ======================================================= */

  const load = async () => {
    setLoading(true);
    setError("");

    try {
      const [
        metricsResponse,
        pointsResponse,
        issuesResponse,
      ] = await Promise.all([
        api.getMetrics(),
        api.getMapPoints(),
        api.listCivicIssues({
          q: query || undefined,
          status:
            status !== "all"
              ? status
              : undefined,
          priority_band:
            priority !== "all"
              ? priority
              : undefined,
          category:
            category !== "all"
              ? category
              : undefined,
        }),
      ]);

      setMetrics(metricsResponse);
      setPoints(pointsResponse);
      setIssues(issuesResponse);
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : "Unable to load command center",
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const timer =
      window.setTimeout(
        () => {
          load();
        },
        220,
      );

    return () =>
      window.clearTimeout(timer);
  }, [
    query,
    status,
    priority,
    category,
  ]);

  /* =======================================================
     ORDERING
     ======================================================= */

  const ordered = useMemo(() => {
    const result = [
      ...issues,
    ];

    if (sort === "attention") {
      result.sort(
        (a, b) =>
          attention(b) -
          attention(a),
      );
    } else if (
      sort === "priority"
    ) {
      result.sort(
        (a, b) =>
          b.priority_score -
          a.priority_score,
      );
    } else {
      result.sort(
        (a, b) =>
          new Date(
            b.created_at,
          ).getTime() -
          new Date(
            a.created_at,
          ).getTime(),
      );
    }

    return result;
  }, [issues, sort]);

  /* =======================================================
     HOTSPOTS
     ======================================================= */

  const hotspots = useMemo(() => {
    const map = new Map<
      string,
      {
        name: string;
        count: number;
        issues: number;
      }
    >();

    for (const issue of points) {
      const name =
        issue.location_name ??
        "Unresolved location";

      const previous =
        map.get(name) ?? {
          name,
          count: 0,
          issues: 0,
        };

      previous.count +=
        issue.complaint_count;

      previous.issues += 1;

      map.set(
        name,
        previous,
      );
    }

    return [
      ...map.values(),
    ]
      .sort(
        (a, b) =>
          b.count - a.count,
      )
      .slice(0, 6);
  }, [points]);

  /* =======================================================
     DEPARTMENT WORKLOAD
     ======================================================= */

  const workload = useMemo(() => {
    const map = new Map<
      string,
      number
    >();

    for (const issue of issues) {
      const key =
        (issue as any)
          .department ||
        "Unassigned";

      map.set(
        key,
        (map.get(key) || 0) + 1,
      );
    }

    return [
      ...map.entries(),
    ]
      .sort(
        (a, b) =>
          b[1] - a[1],
      )
      .slice(0, 6);
  }, [issues]);

  /* =======================================================
     ESCALATION
     ======================================================= */

  const escalation =
    ordered
      .filter(
        (issue) =>
          issue.priority_band ===
            "CRITICAL" ||
          issue.sla_record?.state ===
            "breached" ||
          issue.sla_record?.state ===
            "at_risk",
      )
      .slice(0, 5);

  /* =======================================================
     EXPORT
     ======================================================= */

  const exportCsv = () => {
    const head = [
      "Issue ID",
      "Category",
      "Location",
      "Priority",
      "Score",
      "Status",
      "Reports",
      "Created",
    ];

    const rows = ordered.map(
      (issue) => [
        issue.issue_code,
        CATEGORY_LABELS[
          issue.category
        ] ?? issue.category,
        issue.location_text_raw ??
          "",
        issue.priority_band,
        issue.priority_score,
        issue.status,
        issue.complaint_count,
        new Date(
          issue.created_at,
        ).toISOString(),
      ],
    );

    const csv = [
      head,
      ...rows,
    ]
      .map((row) =>
        row
          .map(
            (value) =>
              `"${String(
                value,
              ).replaceAll(
                '"',
                '""',
              )}"`,
          )
          .join(","),
      )
      .join("\n");

    const url =
      URL.createObjectURL(
        new Blob(
          [csv],
          {
            type: "text/csv",
          },
        ),
      );

    const anchor =
      document.createElement(
        "a",
      );

    anchor.href = url;
    anchor.download =
      "civicfix-command-center.csv";

    anchor.click();

    URL.revokeObjectURL(
      url,
    );
  };

  /* =======================================================
     OPEN CASE
     ======================================================= */

  const openCase = async (
    id: number,
  ) => {
    try {
      setDetail(
        await api.getCivicIssue(
          id,
        ),
      );
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : "Unable to open case",
      );
    }
  };

  /* =======================================================
     RENDER
     ======================================================= */

  return (
    <div className="admin-layout flex min-h-screen">
      {/* ===================================================
          SIDEBAR
          =================================================== */}

      <aside className="admin-sidebar hidden md:flex md:w-[245px] shrink-0 flex-col p-4 sticky top-0 h-screen">
        <Link
          to="/"
          className="flex items-center gap-3 px-2 py-3"
        >
          <div className="brand-mark !shadow-none">
            CF
          </div>

          <div>
            <div className="font-display font-extrabold text-white">
              CivicFix
            </div>

            <div className="text-[10px] text-slate-400">
              Command center
            </div>
          </div>
        </Link>

        <div className="text-[10px] uppercase tracking-[.16em] text-slate-500 px-3 mt-7 mb-2">
          Workspace
        </div>

        <nav className="space-y-1">
          <button
            type="button"
            onClick={() =>
              setView("overview")
            }
            className={`admin-nav w-full text-left px-3 py-2.5 text-sm ${
              view === "overview"
                ? "active"
                : ""
            }`}
          >
            Overview
          </button>

          <button
            type="button"
            onClick={() =>
              setView("cases")
            }
            className={`admin-nav w-full text-left px-3 py-2.5 text-sm ${
              view === "cases"
                ? "active"
                : ""
            }`}
          >
            Case intelligence
          </button>

          <button
            type="button"
            onClick={() =>
              setView("insights")
            }
            className={`admin-nav w-full text-left px-3 py-2.5 text-sm ${
              view === "insights"
                ? "active"
                : ""
            }`}
          >
            Hotspots & workload
          </button>
        </nav>

        <div className="mt-auto rounded-2xl bg-white/5 border border-white/8 p-4">
          <div className="text-[10px] uppercase tracking-widest text-slate-500">
            Signed in
          </div>

          <div className="mt-2 text-sm font-semibold text-white truncate">
            {user?.name}
          </div>

          <div className="text-xs text-slate-400 mt-1 truncate">
            {user?.email}
          </div>
        </div>
      </aside>

      {/* ===================================================
          MAIN
          =================================================== */}

      <main className="flex-1 min-w-0">
        {/* =================================================
            TOP BAR
            ================================================= */}

        <div className="sticky top-0 z-30 bg-white/92 backdrop-blur border-b border-slate-200">
          <div className="max-w-[1500px] mx-auto px-5 md:px-8 py-4">
            <div className="flex flex-wrap gap-3 items-center">
              <div className="md:hidden font-display font-extrabold text-lg">
                CivicFix
              </div>

              <div className="relative flex-1 min-w-[250px]">
                <input
                  className="input-ui !rounded-xl pl-4 pr-4"
                  value={query}
                  onChange={(event) =>
                    setQuery(
                      event.target.value,
                    )
                  }
                  placeholder="Search issue ID, complaint ID, citizen name, email, phone, location…"
                />

                <div className="absolute right-3 top-1/2 -translate-y-1/2 text-[10px] uppercase tracking-widest text-slate-400">
                  Global search
                </div>
              </div>

              <button
                type="button"
                onClick={exportCsv}
                className="btn-secondary !py-2.5"
              >
                Export CSV
              </button>

              <Link
                to="/"
                className="text-sm font-semibold text-slate-500 hover:text-slate-800"
              >
                Exit
              </Link>
            </div>

            <div className="flex flex-wrap gap-2 mt-3">
              <select
                value={status}
                onChange={(event) =>
                  setStatus(
                    event.target.value,
                  )
                }
                className="input-ui !w-auto !py-2 text-sm"
              >
                <option value="all">
                  All statuses
                </option>
                <option value="open">
                  Open
                </option>
                <option value="assigned">
                  Assigned
                </option>
                <option value="in_progress">
                  In progress
                </option>
                <option value="resolved">
                  Resolved
                </option>
              </select>

              <select
                value={priority}
                onChange={(event) =>
                  setPriority(
                    event.target.value,
                  )
                }
                className="input-ui !w-auto !py-2 text-sm"
              >
                <option value="all">
                  All priority
                </option>
                <option value="CRITICAL">
                  Critical
                </option>
                <option value="HIGH">
                  High
                </option>
                <option value="MEDIUM">
                  Medium
                </option>
                <option value="LOW">
                  Low
                </option>
              </select>

              <select
                value={category}
                onChange={(event) =>
                  setCategory(
                    event.target.value,
                  )
                }
                className="input-ui !w-auto !py-2 text-sm"
              >
                <option value="all">
                  All categories
                </option>

                {Object.entries(
                  CATEGORY_LABELS,
                ).map(
                  ([key, value]) => (
                    <option
                      key={key}
                      value={key}
                    >
                      {value}
                    </option>
                  ),
                )}
              </select>

              <select
                value={sort}
                onChange={(event) =>
                  setSort(
                    event.target
                      .value as
                      | "attention"
                      | "newest"
                      | "priority",
                  )
                }
                className="input-ui !w-auto !py-2 text-sm"
              >
                <option value="attention">
                  Sort: attention score
                </option>

                <option value="priority">
                  Sort: priority
                </option>

                <option value="newest">
                  Sort: newest
                </option>
              </select>

              <span className="ml-auto text-xs text-slate-400 self-center">
                Search covers citizen
                name, email and phone
                too.
              </span>
            </div>
          </div>
        </div>

        {/* =================================================
            CONTENT
            ================================================= */}

        <div className="max-w-[1500px] mx-auto px-5 md:px-8 py-7">
          {error && (
            <div className="mb-5 rounded-xl border border-red-100 bg-red-50 text-red-700 p-3 text-sm">
              {error}
            </div>
          )}

          {/* Mobile tabs */}
          <div className="flex flex-wrap md:hidden gap-2 mb-5">
            <button
              type="button"
              onClick={() =>
                setView("overview")
              }
              className={`btn-secondary !py-2 ${
                view === "overview"
                  ? "!bg-indigo-50 !text-indigo-700"
                  : ""
              }`}
            >
              Overview
            </button>

            <button
              type="button"
              onClick={() =>
                setView("cases")
              }
              className={`btn-secondary !py-2 ${
                view === "cases"
                  ? "!bg-indigo-50 !text-indigo-700"
                  : ""
              }`}
            >
              Cases
            </button>

            <button
              type="button"
              onClick={() =>
                setView("insights")
              }
              className={`btn-secondary !py-2 ${
                view === "insights"
                  ? "!bg-indigo-50 !text-indigo-700"
                  : ""
              }`}
            >
              Insights
            </button>
          </div>

          {/* Heading */}
          <div className="flex flex-wrap items-end justify-between gap-4 mb-6">
            <div>
              <div className="text-xs uppercase tracking-[.18em] text-indigo-600 font-bold">
                Civic command center
              </div>

              <h1 className="font-display text-4xl md:text-5xl font-extrabold tracking-[-.04em] mt-2">
                Make the queue explain
                itself.
              </h1>

              <p className="text-slate-500 mt-2">
                Search every case, see where
                service is slipping and open
                the full citizen-to-case trail.
              </p>
            </div>

            {metrics && (
              <div className="text-right">
                <div className="text-xs uppercase tracking-widest text-slate-400">
                  Service compliance
                </div>

                <div className="font-display text-3xl font-extrabold text-indigo-700 mt-1">
                  {
                    metrics.sla_compliance_pct
                  }
                  %
                </div>
              </div>
            )}
          </div>

          {/* =================================================
              KPI CARDS
              ================================================= */}

          <section className="grid grid-cols-2 lg:grid-cols-4 xl:grid-cols-8 gap-3">
            {[
              [
                "Reports",
                metrics?.total_complaints,
                "#334155",
              ],
              [
                "Civic cases",
                metrics?.total_civic_issues,
                "#334155",
              ],
              [
                "Open",
                metrics?.open_issues,
                "#4f46e5",
              ],
              [
                "Critical",
                metrics?.critical_issues,
                "#d64545",
              ],
              [
                "High",
                metrics?.high_issues,
                "#ea580c",
              ],
              [
                "Duplicates",
                metrics?.duplicates_consolidated,
                "#7c3aed",
              ],
              [
                "SLA risk",
                metrics?.sla_at_risk,
                "#c98500",
              ],
              [
                "Breached",
                metrics?.sla_breached,
                "#d64545",
              ],
            ].map(
              ([
                label,
                value,
                color,
              ]) => (
                <div
                  key={String(label)}
                  className="admin-stat"
                >
                  <div className="text-[10px] uppercase tracking-widest text-slate-400">
                    {label}
                  </div>

                  <div
                    className="font-display text-3xl font-extrabold mt-1"
                    style={{
                      color: String(
                        color,
                      ),
                    }}
                  >
                    {value ?? "—"}
                  </div>
                </div>
              ),
            )}
          </section>

          {/* =================================================
              LOADING
              ================================================= */}

          {loading ? (
            <div className="card p-12 text-center text-slate-400 mt-6">
              Refreshing command center…
            </div>
          ) : (
            <>
              {/* =================================================
                  OVERVIEW
                  ================================================= */}

              {view === "overview" && (
                <>
                  <section className="grid xl:grid-cols-[1.28fr_.72fr] gap-5 mt-6">
                    {/* Attention queue */}
                    <div className="card overflow-hidden">
                      <div className="p-5 border-b border-slate-100 flex flex-wrap items-center justify-between gap-3">
                        <div>
                          <div className="text-xs uppercase tracking-widest text-slate-400">
                            Attention queue
                          </div>

                          <div className="font-display text-2xl font-bold mt-1">
                            What should staff
                            look at first
                          </div>
                        </div>

                        <span className="tag bg-indigo-50 text-indigo-700">
                          Transparent score
                        </span>
                      </div>

                      <div className="divide-y divide-slate-100">
                        {ordered
                          .slice(0, 7)
                          .map((issue) => {
                            const [
                              slaText,
                              slaClass,
                            ] =
                              slaLabel(
                                issue
                                  .sla_record
                                  ?.state,
                              );

                            return (
                              <button
                                type="button"
                                key={issue.id}
                                onClick={() =>
                                  openCase(
                                    issue.id,
                                  )
                                }
                                className="table-row w-full text-left p-5 flex items-center gap-4"
                              >
                                <div className="w-10 h-10 rounded-xl bg-slate-100 grid place-items-center text-xs font-bold text-slate-500">
                                  {
                                    issue.complaint_count
                                  }
                                </div>

                                <div className="min-w-0 flex-1">
                                  <div className="flex flex-wrap items-center gap-2">
                                    <span
                                      className={`tag ${priorityClass(
                                        issue.priority_band,
                                      )}`}
                                    >
                                      {
                                        issue.priority_band
                                      }
                                    </span>

                                    <span
                                      className={`tag ${slaClass}`}
                                    >
                                      {slaText}
                                    </span>

                                    <span className="font-mono text-[11px] text-slate-400">
                                      {
                                        issue.issue_code
                                      }
                                    </span>
                                  </div>

                                  <div className="font-semibold truncate mt-2">
                                    {
                                      CATEGORY_LABELS[
                                        issue.category
                                      ]
                                    }{" "}
                                    ·{" "}
                                    {issue.location_text_raw ??
                                      "Location unresolved"}
                                  </div>

                                  <div className="text-sm text-slate-500 truncate mt-1">
                                    {
                                      issue.representative_text
                                    }
                                  </div>
                                </div>

                                <div className="text-right shrink-0">
                                  <div className="text-[10px] uppercase tracking-widest text-slate-400">
                                    Attention
                                  </div>

                                  <div className="font-display text-xl font-extrabold">
                                    {attention(
                                      issue,
                                    )}
                                  </div>

                                  <div className="text-[11px] text-slate-400 mt-1">
                                    {age(
                                      issue.created_at,
                                    )}{" "}
                                    old
                                  </div>
                                </div>
                              </button>
                            );
                          })}

                        {!ordered.length && (
                          <div className="p-10 text-center text-slate-400">
                            No cases match
                            this search.
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Escalation */}
                    <div className="card p-5">
                      <div className="text-xs uppercase tracking-widest text-slate-400">
                        Escalation lane
                      </div>

                      <div className="font-display text-2xl font-bold mt-1">
                        Cases nearing failure
                      </div>

                      <div className="space-y-3 mt-5">
                        {escalation.map(
                          (issue) => (
                            <button
                              type="button"
                              onClick={() =>
                                openCase(
                                  issue.id,
                                )
                              }
                              key={issue.id}
                              className="w-full text-left rounded-xl border border-slate-100 p-4 hover:border-indigo-200"
                            >
                              <div className="flex items-center justify-between gap-3">
                                <span className="font-mono text-xs font-bold">
                                  {
                                    issue.issue_code
                                  }
                                </span>

                                <span
                                  className={`tag ${priorityClass(
                                    issue.priority_band,
                                  )}`}
                                >
                                  {
                                    issue.priority_band
                                  }
                                </span>
                              </div>

                              <div className="font-semibold mt-2">
                                {issue.location_text_raw ??
                                  "Unresolved"}
                              </div>

                              <div className="text-xs text-slate-500 mt-1">
                                {issue
                                  .sla_record
                                  ?.state?.replaceAll(
                                    "_",
                                    " ",
                                  ) ??
                                  "No SLA state"}
                              </div>
                            </button>
                          ),
                        )}

                        {!escalation.length && (
                          <div className="text-sm text-slate-400 py-5">
                            No cases currently
                            need escalation.
                          </div>
                        )}
                      </div>
                    </div>
                  </section>

                  {/* =================================================
                      MAP + HOTSPOTS
                      ================================================= */}

                  <section className="grid xl:grid-cols-[1.25fr_.75fr] gap-5 mt-5">
                    <div className="card overflow-hidden h-[470px]">
                      <div className="p-4 border-b border-slate-100 flex items-center justify-between">
                        <div>
                          <div className="text-xs uppercase tracking-widest text-slate-400">
                            Spatial view
                          </div>

                          <div className="font-display text-xl font-bold mt-1">
                            Where the queue is
                            concentrating
                          </div>
                        </div>

                        <span className="text-xs text-slate-400">
                          {points.length}{" "}
                          mapped cases
                        </span>
                      </div>

                      <div className="h-[408px]">
                        <OperationsMap
                          points={points}
                          selectedId={
                            detail?.id ??
                            null
                          }
                          onSelect={(id) =>
                            openCase(
                              id,
                            )
                          }
                        />
                      </div>
                    </div>

                    <div className="card p-5">
                      <div className="text-xs uppercase tracking-widest text-slate-400">
                        Top recurring places
                      </div>

                      <div className="font-display text-xl font-bold mt-1">
                        Hotspot signal
                      </div>

                      <div className="space-y-4 mt-5">
                        {hotspots.map(
                          (
                            hotspot,
                            index,
                          ) => (
                            <div
                              key={
                                hotspot.name
                              }
                              className="flex items-center gap-3"
                            >
                              <div className="w-7 h-7 rounded-lg bg-indigo-50 text-indigo-700 grid place-items-center text-xs font-bold">
                                {index +
                                  1}
                              </div>

                              <div className="min-w-0 flex-1">
                                <div className="font-semibold truncate">
                                  {
                                    hotspot.name
                                  }
                                </div>

                                <div className="text-xs text-slate-400 mt-1">
                                  {
                                    hotspot.issues
                                  }{" "}
                                  case
                                  {hotspot.issues !==
                                  1
                                    ? "s"
                                    : ""}{" "}
                                  ·{" "}
                                  {
                                    hotspot.count
                                  }{" "}
                                  citizen
                                  report
                                  {hotspot.count !==
                                  1
                                    ? "s"
                                    : ""}
                                </div>
                              </div>
                            </div>
                          ),
                        )}

                        {!hotspots.length && (
                          <div className="text-sm text-slate-400">
                            No mapped
                            hotspots yet.
                          </div>
                        )}
                      </div>
                    </div>
                  </section>
                </>
              )}

              {/* =================================================
                  CASES
                  ================================================= */}

              {view === "cases" && (
                <section className="card overflow-hidden mt-6">
                  <div className="p-5 border-b border-slate-100 flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <div className="text-xs uppercase tracking-widest text-slate-400">
                        Case intelligence
                      </div>

                      <div className="font-display text-2xl font-bold mt-1">
                        Every report, one
                        searchable queue
                      </div>
                    </div>

                    <div className="text-xs text-slate-400">
                      {ordered.length}{" "}
                      results
                    </div>
                  </div>

                  <div className="divide-y divide-slate-100">
                    {ordered.map(
                      (issue) => (
                        <button
                          type="button"
                          key={issue.id}
                          onClick={() =>
                            openCase(
                              issue.id,
                            )
                          }
                          className="table-row w-full text-left p-5 grid lg:grid-cols-[1.2fr_.8fr_.45fr_.45fr] gap-4 items-center"
                        >
                          <div>
                            <div className="flex items-center gap-2">
                              <span
                                className={`tag ${priorityClass(
                                  issue.priority_band,
                                )}`}
                              >
                                {
                                  issue.priority_band
                                }
                              </span>

                              <span
                                className={`tag ${
                                  slaLabel(
                                    issue
                                      .sla_record
                                      ?.state,
                                  )[1]
                                }`}
                              >
                                {
                                  slaLabel(
                                    issue
                                      .sla_record
                                      ?.state,
                                  )[0]
                                }
                              </span>
                            </div>

                            <div className="font-mono text-xs text-slate-400 mt-2">
                              {
                                issue.issue_code
                              }
                            </div>

                            <div className="font-semibold mt-1">
                              {
                                CATEGORY_LABELS[
                                  issue.category
                                ]
                              }
                            </div>

                            <div className="text-sm text-slate-500 truncate mt-1">
                              {
                                issue.representative_text
                              }
                            </div>
                          </div>

                          <div>
                            <div className="text-xs uppercase tracking-widest text-slate-400">
                              Location
                            </div>

                            <div className="text-sm font-semibold mt-1">
                              {issue.location_text_raw ??
                                "Unresolved"}
                            </div>
                          </div>

                          <div>
                            <div className="text-xs uppercase tracking-widest text-slate-400">
                              Reports
                            </div>

                            <div className="font-display text-2xl font-bold mt-1">
                              {
                                issue.complaint_count
                              }
                            </div>
                          </div>

                          <div className="text-right">
                            <div className="text-xs uppercase tracking-widest text-slate-400">
                              Attention
                            </div>

                            <div className="font-display text-2xl font-extrabold mt-1">
                              {attention(
                                issue,
                              )}
                            </div>

                            <div className="text-xs text-slate-400 mt-1">
                              {
                                STATUS_LABELS[
                                  issue.status
                                ]
                              }
                            </div>
                          </div>
                        </button>
                      ),
                    )}

                    {!ordered.length && (
                      <div className="p-12 text-center text-slate-400">
                        No cases matched
                        your filters.
                      </div>
                    )}
                  </div>
                </section>
              )}

              {/* =================================================
                  INSIGHTS
                  ================================================= */}

              {view ===
                "insights" && (
                <section className="grid xl:grid-cols-2 gap-5 mt-6">
                  <div className="card p-6">
                    <div className="text-xs uppercase tracking-widest text-slate-400">
                      Hotspots & recurrence
                    </div>

                    <div className="font-display text-2xl font-bold mt-1">
                      Where problems repeat
                    </div>

                    <div className="space-y-4 mt-6">
                      {hotspots.map(
                        (
                          hotspot,
                          index,
                        ) => (
                          <div
                            key={
                              hotspot.name
                            }
                            className="flex items-center gap-4"
                          >
                            <div className="w-9 h-9 rounded-xl bg-indigo-50 text-indigo-700 grid place-items-center text-sm font-bold">
                              {index +
                                1}
                            </div>

                            <div className="flex-1">
                              <div className="flex justify-between gap-3">
                                <span className="font-semibold">
                                  {
                                    hotspot.name
                                  }
                                </span>

                                <strong>
                                  {
                                    hotspot.count
                                  }
                                </strong>
                              </div>

                              <div className="h-2 bg-slate-100 rounded-full mt-2 overflow-hidden">
                                <div
                                  className="h-full bg-indigo-500 rounded-full"
                                  style={{
                                    width: `${
                                      Math.min(
                                        100,
                                        (hotspot.count /
                                          Math.max(
                                            1,
                                            hotspots[0]
                                              ?.count ??
                                              1,
                                          )) *
                                          100,
                                      )
                                    }%`,
                                  }}
                                />
                              </div>
                            </div>
                          </div>
                        ),
                      )}
                    </div>
                  </div>

                  <div className="card p-6">
                    <div className="text-xs uppercase tracking-widest text-slate-400">
                      Department load
                    </div>

                    <div className="font-display text-2xl font-bold mt-1">
                      Where work is accumulating
                    </div>

                    <div className="space-y-5 mt-6">
                      {workload.map(
                        ([
                          name,
                          count,
                        ]) => (
                          <div key={name}>
                            <div className="flex justify-between text-sm">
                              <span className="font-semibold">
                                {name}
                              </span>

                              <span className="text-slate-500">
                                {count}{" "}
                                cases
                              </span>
                            </div>

                            <div className="h-2 bg-slate-100 rounded-full mt-2 overflow-hidden">
                              <div
                                className="h-full bg-emerald-500 rounded-full"
                                style={{
                                  width: `${Math.min(
                                    100,
                                    (count /
                                      Math.max(
                                        1,
                                        issues.length,
                                      )) *
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

                  <div className="card p-6 xl:col-span-2">
                    <div className="text-xs uppercase tracking-widest text-slate-400">
                      AI operations principles
                    </div>

                    <div className="grid md:grid-cols-3 gap-5 mt-5">
                      <div>
                        <div className="font-semibold">
                          Attention is explainable
                        </div>

                        <p className="text-sm text-slate-500 leading-6 mt-2">
                          Priority, SLA state
                          and recurrence are
                          visible in the queue
                          instead of hiding the
                          reason a case appears
                          first.
                        </p>
                      </div>

                      <div>
                        <div className="font-semibold">
                          Citizen context travels
                          with the case
                        </div>

                        <p className="text-sm text-slate-500 leading-6 mt-2">
                          The detail drawer keeps
                          reporter identity,
                          evidence, related reports
                          and status history together.
                        </p>
                      </div>

                      <div>
                        <div className="font-semibold">
                          Duplicates become one
                          operational unit
                        </div>

                        <p className="text-sm text-slate-500 leading-6 mt-2">
                          Multiple citizen reports
                          can contribute to the same
                          civic issue without creating
                          multiple work queues.
                        </p>
                      </div>
                    </div>
                  </div>
                </section>
              )}
            </>
          )}
        </div>
      </main>

      {/* =====================================================
          CASE DRAWER
          ===================================================== */}

      {detail && (
        <CaseDrawer
          detail={detail}
          points={points}
          onClose={() =>
            setDetail(null)
          }
          onRefresh={() =>
            api
              .getCivicIssue(
                detail.id,
              )
              .then(setDetail)
              .catch(() => {})
          }
        />
      )}
    </div>
  );
}

/* ===========================================================
   CASE DRAWER
   =========================================================== */

function CaseDrawer({
  detail,
  points,
  onClose,
  onRefresh,
}: {
  detail: CivicIssueDetail;
  points: MapPoint[];
  onClose: () => void;
  onRefresh: () => void;
}) {
  const [
    busy,
    setBusy,
  ] = useState(false);

  const [
    note,
    setNote,
  ] = useState("");

  const [
    officer,
    setOfficer,
  ] = useState(
    detail.assigned_to ??
      "",
  );

  const [
    department,
    setDepartment,
  ] = useState(
    detail.department ??
      "Roads & Infrastructure",
  );

  const citizen =
    detail.complaints[0];

  /* =======================================================
     250M IMPACT ZONE
     ======================================================= */

  const IMPACT_RADIUS_METERS =
    250;

  const selectedPoint =
    points.find(
      (point) =>
        point.id === detail.id,
    );

  const nearbyCaseCount =
    selectedPoint
      ? points.filter(
          (point) =>
            distanceMeters(
              selectedPoint.latitude,
              selectedPoint.longitude,
              point.latitude,
              point.longitude,
            ) <=
            IMPACT_RADIUS_METERS,
        ).length
      : 0;

  /* =======================================================
     ACTION
     ======================================================= */

  const action = async (
    kind:
      | "status"
      | "assign",
    value?: string,
  ) => {
    setBusy(true);

    try {
      if (kind === "status") {
        await api.updateStatus(
          detail.id,
          value!,
          "Admin Console",
          note || undefined,
        );
      } else {
        await api.assignIssue(
          detail.id,
          officer,
          department,
        );
      }

      setNote("");

      onRefresh();
    } catch (e) {
      alert(
        e instanceof Error
          ? e.message
          : "Action failed",
      );
    } finally {
      setBusy(false);
    }
  };

  const next =
    detail.status === "open"
      ? [
          "assigned",
          "rejected",
        ]
      : detail.status ===
          "assigned"
        ? [
            "in_progress",
            "open",
          ]
        : detail.status ===
            "in_progress"
          ? [
              "resolved",
              "assigned",
            ]
          : [];

  return (
    <div
      className="fixed inset-0 z-[5000] drawer-layer drawer-backdrop flex justify-end"
      onMouseDown={(event) => {
        if (
          event.target ===
          event.currentTarget
        ) {
          onClose();
        }
      }}
    >
      <aside className="drawer-panel relative z-[5010] w-full max-w-[720px] h-full bg-white overflow-y-auto scroll-clean shadow-2xl">
        {/* =================================================
            HEADER
            ================================================= */}

        <div className="sticky top-0 z-20 bg-white/95 backdrop-blur border-b border-slate-200 px-6 py-5 flex items-start justify-between">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-mono font-bold text-lg">
                {detail.issue_code}
              </span>

              <span
                className={`tag ${priorityClass(
                  detail.priority_band,
                )}`}
              >
                {detail.priority_band} ·{" "}
                {detail.priority_score}
              </span>
            </div>

            <div className="text-sm text-slate-500 mt-2">
              {detail.location_text_raw ??
                "Location unresolved"}{" "}
              · {age(detail.created_at)}{" "}
              old
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="w-9 h-9 rounded-xl border border-slate-200 text-slate-600 hover:bg-slate-50"
          >
            ×
          </button>
        </div>

        <div className="p-6 space-y-5">
          {/* =================================================
              250M SPATIAL IMPACT
              ================================================= */}

          <div className="card p-5 border-indigo-100 bg-indigo-50/40">
            <div className="flex items-start justify-between gap-4">
              <div>
                <div className="text-xs uppercase tracking-widest text-indigo-500 font-bold">
                  Spatial impact
                </div>

                <div className="font-display text-3xl font-extrabold text-slate-800 mt-2">
                  250 m radius
                </div>

                <div className="text-sm text-slate-500 mt-1">
                  Geographic impact zone
                  around this civic case
                </div>
              </div>

              <div className="w-11 h-11 rounded-full border-2 border-indigo-400 bg-indigo-100 grid place-items-center shrink-0">
                <div className="w-3 h-3 rounded-full bg-indigo-600" />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3 mt-5">
              <div className="rounded-xl bg-white border border-indigo-100 p-3">
                <div className="text-[10px] uppercase tracking-wider text-slate-400">
                  Cases inside zone
                </div>

                <div className="font-mono text-2xl font-bold text-slate-800 mt-1">
                  {nearbyCaseCount}
                </div>
              </div>

              <div className="rounded-xl bg-white border border-indigo-100 p-3">
                <div className="text-[10px] uppercase tracking-wider text-slate-400">
                  Current reports
                </div>

                <div className="font-mono text-2xl font-bold text-slate-800 mt-1">
                  {
                    detail.complaint_count
                  }
                </div>
              </div>
            </div>

            <div className="mt-4 pt-4 border-t border-indigo-100">
              <div className="text-xs text-slate-400">
                Spatial signal
              </div>

              <div className="text-sm font-semibold text-slate-700 mt-1">
                {selectedPoint?.location_name ??
                  detail.location_text_raw ??
                  "Mapped coordinates"}
              </div>

              {selectedPoint && (
                <div className="font-mono text-xs text-slate-400 mt-1">
                  {selectedPoint.latitude.toFixed(
                    4,
                  )}
                  ,{" "}
                  {selectedPoint.longitude.toFixed(
                    4,
                  )}
                </div>
              )}

              <div className="text-[11px] text-slate-400 mt-2">
                Proximity is geographic
                context only; it does not
                imply duplicate or causal
                relationship.
              </div>
            </div>
          </div>

          {/* =================================================
              CITIZEN
              ================================================= */}

          <div className="card-soft p-5">
            <div className="text-xs uppercase tracking-widest text-slate-400">
              Citizen
            </div>

            <div className="flex items-start gap-4 mt-3">
              <div className="w-12 h-12 rounded-2xl bg-indigo-100 text-indigo-700 grid place-items-center font-bold">
                {citizen?.citizen_name
                  ?.slice(0, 1)
                  .toUpperCase() ??
                  "?"}
              </div>

              <div className="min-w-0">
                <div className="font-display text-xl font-bold">
                  {citizen?.citizen_name ??
                    "Unknown citizen"}
                </div>

                <div className="text-sm text-slate-500 mt-1">
                  {citizen?.citizen_email ??
                    "No email"}
                </div>

                <div className="text-sm text-slate-500">
                  {citizen?.citizen_phone ??
                    "No phone"}
                </div>
              </div>
            </div>
          </div>

          {/* =================================================
              DECISION TRACE
              ================================================= */}

          <div className="card p-5">
            <div className="text-xs uppercase tracking-widest text-slate-400">
              Decision trace
            </div>

            <div className="mt-4 grid sm:grid-cols-2 gap-3">
              <div className="card-soft p-4">
                <div className="text-xs text-slate-400">
                  AI category
                </div>

                <div className="font-semibold mt-1">
                  {CATEGORY_LABELS[
                    citizen?.category ??
                      detail.category
                  ] ??
                    detail.category}
                </div>

                <div className="text-sm text-slate-500 mt-1">
                  {Math.round(
                    (citizen?.category_confidence ??
                      0) *
                      100,
                  )}
                  % confidence
                </div>
              </div>

              <div className="card-soft p-4">
                <div className="text-xs text-slate-400">
                  Location signal
                </div>

                <div className="font-semibold mt-1">
                  {citizen?.location_text_raw ??
                    "Unresolved"}
                </div>

                <div className="text-sm text-slate-500 mt-1">
                  {Math.round(
                    (citizen?.location_confidence ??
                      0) *
                      100,
                  )}
                  % confidence
                </div>
              </div>
            </div>

            <div className="mt-4 space-y-2">
              {detail.priority_breakdown.map(
                (factor) => (
                  <div
                    key={factor.key}
                    className="flex items-center gap-3"
                  >
                    <div className="w-28 text-xs text-slate-500">
                      {factor.label}
                    </div>

                    <div className="flex-1 h-2 bg-slate-100 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-indigo-500 rounded-full"
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

                    <div className="font-mono text-xs w-10 text-right">
                      {factor.points}/
                      {
                        factor.max_points
                      }
                    </div>
                  </div>
                ),
              )}
            </div>
          </div>

          {/* =================================================
              CITIZEN EVIDENCE
              ================================================= */}

          <div className="card p-5">
            <div className="text-xs uppercase tracking-widest text-slate-400">
              Citizen evidence
            </div>

            <div className="space-y-4 mt-4">
              {detail.complaints
                .flatMap(
                  (complaint) =>
                    complaint.attachments.map(
                      (attachment) => ({
                        complaint,
                        attachment,
                      }),
                    ),
                )
                .map(
                  ({
                    complaint,
                    attachment,
                  }) => (
                    <div
                      key={
                        attachment.id
                      }
                      className="border border-slate-100 rounded-xl p-3"
                    >
                      <div className="flex justify-between gap-3 text-xs">
                        <span className="font-mono">
                          {
                            complaint.complaint_code
                          }
                        </span>

                        <button
                          type="button"
                          disabled={busy}
                          onClick={async () => {
                            setBusy(true);

                            try {
                              await api.verifyAttachment(
                                attachment.id,
                                !attachment.is_verified,
                              );

                              onRefresh();
                            } finally {
                              setBusy(
                                false,
                              );
                            }
                          }}
                          className={`tag ${
                            attachment.is_verified
                              ? "bg-emerald-50 text-emerald-700"
                              : "bg-slate-100 text-slate-600"
                          }`}
                        >
                          {attachment.is_verified
                            ? "Verified evidence"
                            : "Mark verified"}
                        </button>
                      </div>

                      <img
                        src={attachmentUrl(
                          attachment.file_path,
                        )}
                        alt="Citizen evidence"
                        className="mt-3 w-full max-h-64 object-cover rounded-lg"
                      />

                      <div className="text-xs text-slate-500 mt-2">
                        AI signals:{" "}
                        {(
                          attachment.ai_tags ??
                          []
                        ).join(
                          ", ",
                        ) ||
                          "No tags"}{" "}
                        ·{" "}
                        {Math.round(
                          (attachment.ai_confidence ??
                            0) *
                            100,
                        )}
                        %
                      </div>
                    </div>
                  ),
                )}

              {!detail.complaints.some(
                (complaint) =>
                  complaint.attachments
                    ?.length,
              ) && (
                <div className="text-sm text-slate-400">
                  No photo evidence attached.
                </div>
              )}
            </div>
          </div>

          {/* =================================================
              ASSIGNMENT
              ================================================= */}

          <div className="card p-5">
            <div className="text-xs uppercase tracking-widest text-slate-400">
              Assignment
            </div>

            <div className="grid sm:grid-cols-2 gap-3 mt-4">
              <div>
                <label className="text-xs text-slate-500">
                  Officer
                </label>

                <input
                  value={officer}
                  onChange={(event) =>
                    setOfficer(
                      event.target.value,
                    )
                  }
                  className="input-ui mt-1"
                  placeholder="Officer / team"
                />
              </div>

              <div>
                <label className="text-xs text-slate-500">
                  Department
                </label>

                <select
                  value={department}
                  onChange={(event) =>
                    setDepartment(
                      event.target.value,
                    )
                  }
                  className="input-ui mt-1"
                >
                  <option>
                    Roads & Infrastructure
                  </option>
                  <option>
                    Sanitation
                  </option>
                  <option>
                    Street Lighting
                  </option>
                  <option>
                    Drainage
                  </option>
                  <option>
                    Water Supply
                  </option>
                  <option>
                    General Works
                  </option>
                </select>
              </div>
            </div>

            <button
              type="button"
              disabled={
                !officer || busy
              }
              onClick={() =>
                action("assign")
              }
              className="btn-primary mt-4"
            >
              {busy
                ? "Saving…"
                : "Save assignment"}
            </button>
          </div>

          {/* =================================================
              WORKFLOW
              ================================================= */}

          <div className="card p-5">
            <div className="text-xs uppercase tracking-widest text-slate-400">
              Workflow
            </div>

            <div className="grid sm:grid-cols-2 gap-2 mt-4">
              {next.map(
                (nextStatus) => (
                  <button
                    type="button"
                    disabled={busy}
                    key={nextStatus}
                    onClick={() =>
                      action(
                        "status",
                        nextStatus,
                      )
                    }
                    className={`btn-secondary ${
                      nextStatus ===
                      "resolved"
                        ? "!border-emerald-200 !text-emerald-700 !bg-emerald-50"
                        : ""
                    }`}
                  >
                    {nextStatus.replaceAll(
                      "_",
                      " ",
                    )}
                  </button>
                ),
              )}
            </div>

            <label className="block mt-4">
              <span className="text-xs text-slate-500">
                Decision note
              </span>

              <textarea
                value={note}
                onChange={(event) =>
                  setNote(
                    event.target.value,
                  )
                }
                className="input-ui mt-1 min-h-24"
                placeholder="Why was this status change or escalation made?"
              />
            </label>
          </div>

          {/* =================================================
              DUPLICATE CLUSTER
              ================================================= */}

          <div className="card p-5">
            <div className="text-xs uppercase tracking-widest text-slate-400">
              Duplicate cluster
            </div>

            <div className="font-display text-2xl font-bold mt-1">
              {detail.complaint_count}{" "}
              citizen report
              {detail.complaint_count !==
              1
                ? "s"
                : ""}{" "}
              consolidated
            </div>

            <div className="space-y-2 mt-4">
              {detail.complaints.map(
                (complaint) => (
                  <div
                    key={
                      complaint.id
                    }
                    className="rounded-xl bg-slate-50 p-3"
                  >
                    <div className="flex justify-between text-xs">
                      <span className="font-mono font-bold">
                        {
                          complaint.complaint_code
                        }
                      </span>

                      <span className="text-slate-400">
                        {new Date(
                          complaint.created_at,
                        ).toLocaleString()}
                      </span>
                    </div>

                    <div className="text-sm mt-2 text-slate-600">
                      {
                        complaint.raw_text
                      }
                    </div>
                  </div>
                ),
              )}
            </div>
          </div>

          {/* =================================================
              ACCOUNTABILITY TIMELINE
              ================================================= */}

          <div className="card p-5">
            <div className="text-xs uppercase tracking-widest text-slate-400">
              Accountability timeline
            </div>

            <div className="space-y-4 mt-5">
              {detail.status_history.map(
                (history, index) => (
                  <div
                    key={`${history.changed_at}-${index}`}
                    className="flex gap-3"
                  >
                    <div className="w-2 h-2 rounded-full bg-indigo-500 mt-2 shrink-0" />

                    <div>
                      <div className="flex flex-wrap gap-2 items-center">
                        <span className="font-semibold">
                          {STATUS_LABELS[
                            history.to_status
                          ] ??
                            history.to_status}
                        </span>

                        <span className="text-xs text-slate-400">
                          {new Date(
                            history.changed_at,
                          ).toLocaleString()}
                        </span>
                      </div>

                      <div className="text-sm text-slate-500 mt-1">
                        {history.note ??
                          "Status changed"}{" "}
                        ·{" "}
                        {history.changed_by ??
                          "System"}
                      </div>
                    </div>
                  </div>
                ),
              )}
            </div>
          </div>
        </div>
      </aside>
    </div>
  );
}