import { Routes, Route } from "react-router-dom";
import Home from "./pages/Home";
import ReportIssue from "./pages/ReportIssue";
import TrackComplaint from "./pages/TrackComplaint";
import MyComplaints from "./pages/MyComplaints";
import AdminConsole from "./pages/AdminConsole";
import AuthPage from "./pages/AuthPage";
import ProtectedRoute from "./components/common/ProtectedRoute";

export default function App() {
  return <Routes>
    <Route path="/" element={<Home />} />
    <Route path="/login" element={<AuthPage mode="login" />} />
    <Route path="/register" element={<AuthPage mode="register" />} />

    <Route element={<ProtectedRoute role="citizen" />}>
      <Route path="/report" element={<ReportIssue />} />
      <Route path="/complaints" element={<MyComplaints />} />
      <Route path="/track" element={<MyComplaints />} />
      <Route path="/track/:code" element={<TrackComplaint />} />
    </Route>

    <Route element={<ProtectedRoute role="admin" />}>
      <Route path="/admin" element={<AdminConsole />} />
    </Route>
  </Routes>;
}
