import {
  CircleMarker,
  MapContainer,
  Popup,
  ScaleControl,
  TileLayer,
  useMap,
  ZoomControl,
} from "react-leaflet";
import { useEffect, useMemo, useRef } from "react";
import type { MapPoint, PriorityBand } from "../../types";
import {
  PRIORITY_COLORS,
  CATEGORY_LABELS,
  STATUS_LABELS,
} from "../../types";

const CENTER: [number, number] = [18.5205, 73.849];

function FitToPoints({ points }: { points: MapPoint[] }) {
  const map = useMap();
  const previousSignature = useRef("");

  const signature = useMemo(
    () =>
      points
        .map((point) => `${point.id}:${point.latitude}:${point.longitude}`)
        .sort()
        .join("|"),
    [points],
  );

  useEffect(() => {
    if (!points.length || previousSignature.current === signature) return;
    previousSignature.current = signature;

    if (points.length === 1) {
      map.setView(
        [points[0].latitude, points[0].longitude],
        15,
        { animate: true },
      );
      return;
    }

    map.fitBounds(
      points.map(
        (point) => [point.latitude, point.longitude] as [number, number],
      ),
      { padding: [50, 50], maxZoom: 16, animate: true },
    );
  }, [map, points, signature]);

  return null;
}

function FocusSelected({
  points,
  selectedId,
}: {
  points: MapPoint[];
  selectedId?: number | null;
}) {
  const map = useMap();

  useEffect(() => {
    if (selectedId == null) return;
    const point = points.find((item) => item.id === selectedId);
    if (!point) return;

    // The case drawer is the primary interaction when a case is selected.
    map.closePopup();
    map.flyTo(
      [point.latitude, point.longitude],
      Math.max(map.getZoom(), 16),
      { duration: 0.8 },
    );
  }, [map, points, selectedId]);

  return null;
}

function MapActions({ points }: { points: MapPoint[] }) {
  const map = useMap();

  const fitAll = () => {
    if (!points.length) {
      map.setView(CENTER, 14, { animate: true });
      return;
    }

    if (points.length === 1) {
      map.setView(
        [points[0].latitude, points[0].longitude],
        15,
        { animate: true },
      );
      return;
    }

    map.fitBounds(
      points.map(
        (point) => [point.latitude, point.longitude] as [number, number],
      ),
      { padding: [50, 50], maxZoom: 16, animate: true },
    );
  };

  const centerCity = () => {
    map.flyTo(CENTER, 14, { duration: 0.7 });
  };

  return (
    <div className="absolute top-3 right-3 z-[400] flex flex-col gap-2">
      <button
        type="button"
        onClick={fitAll}
        className="bg-white border border-slate-200 shadow-sm rounded-lg px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
      >
        Fit cases
      </button>
      <button
        type="button"
        onClick={centerCity}
        className="bg-white border border-slate-200 shadow-sm rounded-lg px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
      >
        Center
      </button>
    </div>
  );
}

function MapLegend() {
  const priorities: PriorityBand[] = [
    "CRITICAL",
    "HIGH",
    "MEDIUM",
    "LOW",
  ];

  return (
    <div className="absolute bottom-3 left-3 z-[400] bg-white/95 backdrop-blur border border-slate-200 rounded-xl shadow-sm p-3">
      <div className="text-[10px] uppercase tracking-widest text-slate-400 font-bold mb-2">
        Priority
      </div>
      <div className="space-y-1.5">
        {priorities.map((priority) => (
          <div key={priority} className="flex items-center gap-2">
            <span
              className="w-2.5 h-2.5 rounded-full"
              style={{ backgroundColor: PRIORITY_COLORS[priority] }}
            />
            <span className="text-[11px] font-medium text-slate-600">
              {priority}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function getMarkerRadius(point: MapPoint) {
  const base =
    point.priority_band === "CRITICAL"
      ? 10
      : point.priority_band === "HIGH"
        ? 9
        : point.priority_band === "MEDIUM"
          ? 8
          : 7;

  const recurrenceBoost = Math.min(
    5,
    Math.max(0, point.complaint_count - 1),
  );

  return base + recurrenceBoost;
}

function markerOpacity(status: string) {
  if (status === "resolved") return 0.42;
  if (status === "rejected") return 0.28;
  return 0.82;
}

export default function OperationsMap({
  points,
  onSelect,
  selectedId,
}: {
  points: MapPoint[];
  onSelect: (id: number) => void;
  selectedId?: number | null;
}) {
  return (
    <div className="relative isolate z-0 h-full w-full overflow-hidden bg-slate-100">
      <MapContainer
        center={CENTER}
        zoom={14}
        scrollWheelZoom
        zoomControl={false}
        className="relative z-0 h-full w-full"
        style={{ height: "100%", width: "100%" }}
      >
        <TileLayer
          attribution="&copy; OpenStreetMap contributors"
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        <ZoomControl position="bottomright" />
        <ScaleControl position="bottomright" />
        <FitToPoints points={points} />
        <FocusSelected points={points} selectedId={selectedId} />
        <MapActions points={points} />

        {points.map((point) => {
          const color = PRIORITY_COLORS[point.priority_band];
          const selected = selectedId === point.id;
          const radius = getMarkerRadius(point);

          return (
            <CircleMarker
              key={point.id}
              center={[point.latitude, point.longitude]}
              radius={selected ? radius + 5 : radius}
              pathOptions={{
                color,
                fillColor: color,
                fillOpacity: selected
                  ? 0.95
                  : markerOpacity(point.status),
                weight: selected ? 4 : 2,
                opacity: selected ? 1 : 0.8,
              }}
              eventHandlers={{
                click: () => onSelect(point.id),
              }}
            >
              <Popup>
                <div className="min-w-[245px] p-1">
                  <div className="flex items-center justify-between gap-3">
                    <span className="font-mono text-[10px] font-bold text-slate-400">
                      {point.issue_code}
                    </span>
                    <span
                      className="text-[10px] font-bold"
                      style={{ color }}
                    >
                      {point.priority_band}
                    </span>
                  </div>

                  <div className="font-semibold text-slate-800 mt-3">
                    {CATEGORY_LABELS[point.category] ?? point.category}
                  </div>

                  <div className="text-xs text-slate-500 mt-1">
                    {point.location_name ?? "Mapped coordinates"}
                  </div>

                  <div className="grid grid-cols-2 gap-2 mt-4">
                    <div className="rounded-lg bg-slate-50 p-2">
                      <div className="text-[9px] uppercase tracking-wider text-slate-400">
                        Priority
                      </div>
                      <div className="font-mono font-bold text-sm mt-0.5">
                        {point.priority_score}/100
                      </div>
                    </div>
                    <div className="rounded-lg bg-slate-50 p-2">
                      <div className="text-[9px] uppercase tracking-wider text-slate-400">
                        Reports
                      </div>
                      <div className="font-mono font-bold text-sm mt-0.5">
                        {point.complaint_count}
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center justify-between gap-3 mt-4 text-xs">
                    <span className="text-slate-400">Status</span>
                    <span className="font-semibold text-slate-700">
                      {STATUS_LABELS[point.status] ?? point.status}
                    </span>
                  </div>

                  <div className="flex items-center justify-between gap-3 mt-2 text-xs">
                    <span className="text-slate-400">Coordinates</span>
                    <span className="font-mono text-slate-500">
                      {point.latitude.toFixed(4)}, {point.longitude.toFixed(4)}
                    </span>
                  </div>

                  <button
                    type="button"
                    onClick={() => onSelect(point.id)}
                    className="btn-primary w-full !py-2 mt-4 text-xs"
                  >
                    Open case
                  </button>
                </div>
              </Popup>
            </CircleMarker>
          );
        })}
      </MapContainer>

      {points.length === 0 && (
        <div className="absolute inset-0 z-[300] grid place-items-center pointer-events-none">
          <div className="bg-white/95 border border-slate-200 rounded-2xl shadow-sm px-6 py-5 text-center">
            <div className="text-sm font-semibold text-slate-700">
              No mapped cases
            </div>
            <div className="text-xs text-slate-400 mt-1">
              Cases with verified coordinates will appear here.
            </div>
          </div>
        </div>
      )}

      {points.length > 0 && (
        <>
          <MapLegend />
          <div className="absolute top-3 left-3 z-[400] bg-white/95 backdrop-blur border border-slate-200 rounded-xl shadow-sm px-3 py-2">
            <div className="text-[10px] uppercase tracking-widest text-slate-400">
              Live spatial queue
            </div>
            <div className="font-display text-lg font-bold text-slate-800">
              {points.length} mapped case{points.length !== 1 ? "s" : ""}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
