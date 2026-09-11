import { Navigate, Route, BrowserRouter, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "./auth";
import { LoginPage } from "./pages/Login";
import { OverviewPage } from "./pages/Overview";
import { MetersPage } from "./pages/Meters";
import { VeePage } from "./pages/Vee";
import { ConsumptionPage } from "./pages/Consumption";
import { ControlPage } from "./pages/Control";
import { ObservabilityPage } from "./pages/Observability";
import { ConfigurationPage } from "./pages/Configuration";

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuth();
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/" element={<RequireAuth><OverviewPage /></RequireAuth>} />
      <Route path="/meters" element={<RequireAuth><MetersPage /></RequireAuth>} />
      <Route path="/vee" element={<RequireAuth><VeePage /></RequireAuth>} />
      <Route path="/consumption" element={<RequireAuth><ConsumptionPage /></RequireAuth>} />
      <Route path="/control" element={<RequireAuth><ControlPage /></RequireAuth>} />
      <Route path="/observability" element={<RequireAuth><ObservabilityPage /></RequireAuth>} />
      <Route path="/configuration" element={<RequireAuth><ConfigurationPage /></RequireAuth>} />
    </Routes>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </AuthProvider>
  );
}
