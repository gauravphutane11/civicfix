import { useEffect, useRef, useState } from "react";

export interface LivePhotoCaptureResult {
  file: File;
  latitude: number;
  longitude: number;
  accuracy: number | null;
}

interface LivePhotoCaptureProps {
  label?: string;
  hint?: string;
  disabled?: boolean;
  onCapture: (result: LivePhotoCaptureResult) => Promise<void> | void;
}

export default function LivePhotoCapture({
  label = "Take live photo",
  hint = "Camera capture only. File selection is not available.",
  disabled = false,
  onCapture,
}: LivePhotoCaptureProps) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const stop = () => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    setOpen(false);
  };

  useEffect(() => stop, []);

  const openCamera = async () => {
    setError("");
    if (disabled) return;
    if (!navigator.mediaDevices?.getUserMedia) {
      setError("Live camera is not supported by this browser.");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: { ideal: "environment" },
          width: { ideal: 1920 },
          height: { ideal: 1080 },
        },
        audio: false,
      });
      streamRef.current = stream;
      setOpen(true);
      requestAnimationFrame(() => {
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          videoRef.current.play().catch(() => undefined);
        }
      });
    } catch {
      setError("Camera access was denied or unavailable. Please allow camera permission and try again.");
    }
  };

  const capture = async () => {
    const video = videoRef.current;
    if (!video || video.readyState < 2) {
      setError("Camera is not ready yet. Please wait a moment and try again.");
      return;
    }
    if (!navigator.geolocation) {
      setError("Location access is required for live evidence.");
      return;
    }

    setBusy(true);
    setError("");
    try {
      const position = await new Promise<GeolocationPosition>((resolve, reject) => {
        navigator.geolocation.getCurrentPosition(resolve, reject, {
          enableHighAccuracy: true,
          timeout: 15000,
          maximumAge: 0,
        });
      });

      const canvas = document.createElement("canvas");
      canvas.width = video.videoWidth || 1280;
      canvas.height = video.videoHeight || 720;
      const context = canvas.getContext("2d");
      if (!context) throw new Error("Could not prepare the camera image.");
      context.drawImage(video, 0, 0, canvas.width, canvas.height);

      const blob = await new Promise<Blob>((resolve, reject) => {
        canvas.toBlob((value) => (value ? resolve(value) : reject(new Error("Could not capture the camera image."))), "image/jpeg", 0.92);
      });
      const file = new File([blob], `civicfix-live-${Date.now()}.jpg`, { type: "image/jpeg" });
      stop();
      await onCapture({
        file,
        latitude: position.coords.latitude,
        longitude: position.coords.longitude,
        accuracy: position.coords.accuracy ?? null,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to capture live evidence.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-xs uppercase tracking-widest text-slate-500 font-bold">Live camera evidence</div>
          <div className="font-semibold text-slate-800 mt-1">{label}</div>
          <p className="text-xs text-slate-500 mt-1">{hint}</p>
        </div>
        {!open && (
          <button type="button" className="btn-primary" onClick={openCamera} disabled={disabled}>
            Open camera
          </button>
        )}
      </div>

      {error && <div className="mt-3 rounded-xl bg-red-50 border border-red-100 px-3 py-2 text-sm text-red-700">{error}</div>}

      {open && (
        <div className="mt-4 rounded-2xl bg-slate-950 p-2">
          <video ref={videoRef} autoPlay playsInline muted className="w-full max-h-[420px] rounded-xl object-cover" />
          <div className="flex flex-wrap gap-2 p-2">
            <button type="button" className="btn-primary" onClick={() => void capture()} disabled={busy}>
              {busy ? "Capturing…" : "Capture live photo"}
            </button>
            <button type="button" className="btn-secondary" onClick={stop} disabled={busy}>
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
