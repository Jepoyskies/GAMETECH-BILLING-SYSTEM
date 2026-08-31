import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { lazy, Suspense } from "react";
import { AuthProvider, useAuth } from "./context/AuthContext";
import { ToastProvider } from "./context/ToastContext";
import Sidebar from "./components/Sidebar";
import CustomScrollbar from "./components/CustomScrollbar";
import ForcePasswordChange from "./components/ForcePasswordChange";
import "./App.css";
import "./styles/Toast.css";
import "./styles/Forms.css";
import "./styles/ListPage.css";
import "./styles/Filters.css";

const Login = lazy(() => import("./pages/Login"));
const Dashboard = lazy(() => import("./pages/Dashboard"));
const DispatchMonitoring = lazy(() => import("./pages/DispatchMonitoring"));
const InternetInstall = lazy(() => import("./pages/InternetInstall"));
const CignalInstall = lazy(() => import("./pages/CignalInstall"));
const ClientConcerns = lazy(() => import("./pages/ClientConcerns"));
const Customers = lazy(() => import("./pages/Customers"));
const CustomerDashboard = lazy(() => import("./pages/CustomerDashboard"));
const StaffManagement = lazy(() => import("./pages/StaffManagement"));
const AuditLog = lazy(() => import("./pages/AuditLog"));
const Backups = lazy(() => import("./pages/Backups"));

function AppRoutes() {
  const { user, loading, mustChangePassword } = useAuth();

  const fallback = <div className="app-loading">Loading…</div>;

  if (loading) {
    return fallback;
  }

  if (!user) {
    return (
      <Suspense fallback={fallback}>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
      </Suspense>
    );
  }

  if (mustChangePassword) {
    return <ForcePasswordChange />;
  }

  return (
    <div className="app-layout">
      <Sidebar />
      <main className="app-main">
        <div className="app-main-inner">
          <Suspense fallback={fallback}>
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/dispatches" element={<DispatchMonitoring />} />
              <Route path="/internet-install" element={<InternetInstall />} />
              <Route path="/cignal-install" element={<CignalInstall />} />
              <Route path="/client-concerns" element={<ClientConcerns />} />
              <Route path="/customers" element={<Customers />} />
              <Route path="/customers/:id" element={<CustomerDashboard />} />
              <Route path="/staff" element={<StaffManagement />} />
              <Route path="/backups" element={<Backups />} />
              <Route path="/audit-log" element={<AuditLog />} />
              <Route path="/login" element={<Navigate to="/" replace />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </Suspense>
        </div>
      </main>
    </div>
  );
}

function App() {
  return (
    <BrowserRouter>
      <ToastProvider>
        <AuthProvider>
          <CustomScrollbar />
          <AppRoutes />
        </AuthProvider>
      </ToastProvider>
    </BrowserRouter>
  );
}

export default App;