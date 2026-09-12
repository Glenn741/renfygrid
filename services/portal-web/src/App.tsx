import { Navigate, Route, BrowserRouter, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "./auth";
import { LoginPage } from "./pages/Login";
import { OverviewPage } from "./pages/Overview";
import { MetersPage } from "./pages/Meters";
import { VeePage } from "./pages/Vee";
import { ConsumptionPage } from "./pages/Consumption";
import { ControlPage } from "./pages/Control";
import { NetworkBalancePage } from "./pages/NetworkBalance";
import { NetworkModelPage } from "./pages/NetworkModel";
import { ObservabilityPage } from "./pages/Observability";
import { IntegrationsPage } from "./pages/Integrations";
import { ConfigurationPage } from "./pages/Configuration";
import { ControlOrderDetailPage } from "./pages/ControlOrderDetail";

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
      <Route path="/control/:orderId" element={<RequireAuth><ControlOrderDetailPage /></RequireAuth>} />
      <Route path="/network-balance" element={<RequireAuth><NetworkBalancePage /></RequireAuth>} />
      <Route path="/network-model" element={<RequireAuth><NetworkModelPage /></RequireAuth>} />
      <Route path="/observability" element={<RequireAuth><ObservabilityPage /></RequireAuth>} />
      <Route path="/integrations" element={<RequireAuth><IntegrationsPage /></RequireAuth>} />
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
