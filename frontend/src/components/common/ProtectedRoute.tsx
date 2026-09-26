import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../../auth";

export default function ProtectedRoute({ role }: { role?: string }) {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return <div className="min-h-screen civic-app grid place-items-center text-sm font-semibold text-slate-500">AUTHENTICATING…</div>;
  }

  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  if (role && user.role !== role) return <Navigate to="/" replace />;

  return <Outlet />;
}
