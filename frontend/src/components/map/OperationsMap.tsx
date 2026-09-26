import {
  Circle,
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
import { PRIORITY_COLORS, CATEGORY_LABELS, STATUS_LABELS } from "../../types";

const CENTER: [number, number] = [18.5205, 73.849];
const IMPACT_RADIUS_METERS = 250;

function distanceMeters(lat1:number, lon1:number, lat2:number, lon2:number) {
  const earthRadius = 6371000;
  const rad = (value:number) => value * Math.PI / 180;
  const dLat = rad(lat2 - lat1);
  const dLon = rad(lon2 - lon1);
  const a = Math.sin(dLat / 2) ** 2 + Math.cos(rad(lat1)) * Math.cos(rad(lat2)) * Math.sin(dLon / 2) ** 2;
  return earthRadius * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

function FitToPoints({ points }:{points:MapPoint[]}) {
  const map = useMap();
  const previousSignature = useRef("");
  const signature = useMemo(() => points.map(p => `${p.id}:${p.latitude}:${p.longitude}`).sort().join("|"), [points]);

  useEffect(() => {
    if (!points.length || previousSignature.current === signature) return;
    previousSignature.current = signature;
    if (points.length === 1) {
      map.setView([points[0].latitude, points[0].longitude], 15, { animate: true });
      return;
    }
    map.fitBounds(points.map(p => [p.latitude, p.longitude] as [number, number]), { padding: [50, 50], maxZoom: 16, animate: true });
  }, [map, points, signature]);

  return null;
}

function FocusSelected({ points, selectedId }:{points:MapPoint[];selectedId?:number|null}) {
  const map = useMap();
  useEffect(() => {
    if (selectedId == null) return;
    const point = points.find(p => p.id === selectedId);
    if (!point) return;
    map.closePopup();
    map.flyTo([point.latitude, point.longitude], Math.max(map.getZoom(), 16), { duration: 0.8 });
  }, [map, points, selectedId]);
  return null;
}

function MapActions({ points }:{points:MapPoint[]}) {
  const map = useMap();
  const fitAll = () => {
    if (!points.length) return map.setView(CENTER, 14, { animate: true });
    if (points.length === 1) return map.setView([points[0].latitude, points[0].longitude], 15, { animate: true });
    map.fitBounds(points.map(p => [p.latitude, p.longitude] as [number, number]), { padding: [50, 50], maxZoom: 16, animate: true });
  };
  const centerCity = () => map.flyTo(CENTER, 14, { duration: 0.7 });
  return <div className="absolute top-3 right-3 z-[400] flex flex-col gap-2">
    <button type="button" onClick={fitAll} className="map-action-btn">Fit cases</button>
    <button type="button" onClick={centerCity} className="map-action-btn">Center</button>
  </div>;
}

function MapLegend() {
  const priorities: PriorityBand[] = ["CRITICAL", "HIGH", "MEDIUM", "LOW"];
  return <div className="absolute bottom-3 left-3 z-[400] map-legend">
    <div className="map-legend-title">Priority</div>
    <div className="space-y-1.5">{priorities.map(priority => <div key={priority} className="flex items-center gap-2">
      <span className="w-2.5 h-2.5 rounded-full" style={{backgroundColor: PRIORITY_COLORS[priority]}} />
      <span className="text-[11px] font-medium text-slate-600">{priority}</span>
    </div>)}</div>
  </div>;
}

function getMarkerRadius(point:MapPoint) {
  const base = point.priority_band === "CRITICAL" ? 10 : point.priority_band === "HIGH" ? 9 : point.priority_band === "MEDIUM" ? 8 : 7;
  return base + Math.min(5, Math.max(0, point.complaint_count - 1));
}

function markerOpacity(status:string) {
  if (status === "resolved") return 0.42;
  if (status === "rejected") return 0.28;
  return 0.82;
}

export default function OperationsMap({ points, onSelect, selectedId }:{points:MapPoint[];onSelect:(id:number)=>void;selectedId?:number|null}) {
  const selectedPoint = selectedId == null ? null : points.find(p => p.id === selectedId) ?? null;
  const nearbyCount = selectedPoint ? points.filter(p => distanceMeters(selectedPoint.latitude, selectedPoint.longitude, p.latitude, p.longitude) <= IMPACT_RADIUS_METERS).length : 0;

  return <div className="relative isolate z-0 h-full w-full overflow-hidden bg-slate-100">
    <MapContainer center={CENTER} zoom={14} scrollWheelZoom zoomControl={false} className="relative z-0 h-full w-full" style={{height:"100%",width:"100%"}}>
      <TileLayer attribution="&copy; OpenStreetMap contributors" url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
      <ZoomControl position="bottomright" />
      <ScaleControl position="bottomright" />
      <FitToPoints points={points} />
      <FocusSelected points={points} selectedId={selectedId} />
      <MapActions points={points} />

      {selectedPoint && <Circle center={[selectedPoint.latitude, selectedPoint.longitude]} radius={IMPACT_RADIUS_METERS} pathOptions={{color: PRIORITY_COLORS[selectedPoint.priority_band], weight: 2, opacity: .75, fillColor: PRIORITY_COLORS[selectedPoint.priority_band], fillOpacity: .07, dashArray:"8 8"}} interactive={false} />}

      {points.map(point => {
        const color = PRIORITY_COLORS[point.priority_band];
        const selected = selectedId === point.id;
        const radius = getMarkerRadius(point);
        return <CircleMarker key={point.id} center={[point.latitude, point.longitude]} radius={selected ? radius + 5 : radius} pathOptions={{color,fillColor:color,fillOpacity:selected?.95:markerOpacity(point.status),weight:selected?4:2,opacity:selected?1:.8}} eventHandlers={{click:()=>onSelect(point.id)}}>
          <Popup>
            <div className="min-w-[245px] p-1">
              <div className="flex items-center justify-between gap-3"><span className="font-mono text-[10px] font-bold text-slate-400">{point.issue_code}</span><span className="text-[10px] font-bold" style={{color}}>{point.priority_band}</span></div>
              <div className="font-semibold text-slate-800 mt-3">{CATEGORY_LABELS[point.category] ?? point.category}</div>
              <div className="text-xs text-slate-500 mt-1">{point.location_name ?? "Mapped coordinates"}</div>
              <div className="grid grid-cols-2 gap-2 mt-4"><div className="rounded-lg bg-slate-50 p-2"><div className="text-[9px] uppercase tracking-wider text-slate-400">Priority</div><div className="font-mono font-bold text-sm mt-0.5">{point.priority_score}/100</div></div><div className="rounded-lg bg-slate-50 p-2"><div className="text-[9px] uppercase tracking-wider text-slate-400">Reports</div><div className="font-mono font-bold text-sm mt-0.5">{point.complaint_count}</div></div></div>
              <div className="flex items-center justify-between gap-3 mt-4 text-xs"><span className="text-slate-400">Status</span><span className="font-semibold text-slate-700">{STATUS_LABELS[point.status] ?? point.status}</span></div>
              <div className="flex items-center justify-between gap-3 mt-2 text-xs"><span className="text-slate-400">Coordinates</span><span className="font-mono text-slate-500">{point.latitude.toFixed(4)}, {point.longitude.toFixed(4)}</span></div>
              <button type="button" onClick={()=>onSelect(point.id)} className="btn-primary w-full !py-2 mt-4 text-xs">Open case</button>
            </div>
          </Popup>
        </CircleMarker>;
      })}
    </MapContainer>

    {selectedPoint && <div className="absolute top-3 left-3 z-[450] spatial-impact-card">
      <div className="text-[10px] uppercase tracking-widest text-indigo-500 font-bold">Impact zone</div>
      <div className="text-lg font-bold text-slate-800 mt-0.5">250 m radius</div>
      <div className="text-xs text-slate-400 mt-1">Geographic context around selected case</div>
      <div className="mt-3 pt-3 border-t border-slate-100 flex items-end justify-between gap-5"><div><div className="text-[10px] uppercase tracking-wider text-slate-400">Mapped cases inside</div><div className="font-mono text-xl font-bold text-slate-800 mt-0.5">{nearbyCount}</div></div><span className="text-[10px] text-slate-400">250 metres</span></div>
    </div>}

    {points.length === 0 && <div className="absolute inset-0 z-[300] grid place-items-center pointer-events-none"><div className="bg-white/95 border border-slate-200 rounded-2xl shadow-sm px-6 py-5 text-center"><div className="text-sm font-semibold text-slate-700">No mapped cases</div><div className="text-xs text-slate-400 mt-1">Cases with verified coordinates will appear here.</div></div></div>}
    <MapLegend />
    {points.length > 0 && !selectedPoint && <div className="absolute top-3 left-3 z-[400] spatial-queue-card"><div className="text-[10px] uppercase tracking-widest text-slate-400">Live spatial queue</div><div className="font-display text-lg font-bold text-slate-800">{points.length} mapped case{points.length !== 1 ? "s" : ""}</div></div>}
  </div>;
}
