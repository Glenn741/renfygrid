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
import { DigitalTwinPage } from "./pages/DigitalTwin";
import { MaintenancePage } from "./pages/Maintenance";
import { ObservabilityPage } from "./pages/Observability";
import { IntegrationsPage } from "./pages/Integrations";
import { ConfigurationPage } from "./pages/Configuration";
import { ControlOrderDetailPage } from "./pages/ControlOrderDetail";
import { SystemPage } from "./pages/System";
import { OperationsPage } from "./pages/Operations";
import { OperatorPage } from "./pages/Operator";
import { QualityPage } from "./pages/Quality";
import { EmergenciesPage } from "./pages/Emergencies";
import { WarehousePage } from "./pages/Warehouse";
import { SanitationPage } from "./pages/Sanitation";
import { ImprovementPage } from "./pages/Improvement";
import { InspectionsPage } from "./pages/Inspections";

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
      <Route path="/system" element={<RequireAuth><SystemPage /></RequireAuth>} />
      <Route path="/operations" element={<RequireAuth><OperationsPage /></RequireAuth>} />
      <Route path="/operator" element={<RequireAuth><OperatorPage /></RequireAuth>} />
      <Route path="/quality" element={<RequireAuth><QualityPage /></RequireAuth>} />
      <Route path="/emergencies" element={<RequireAuth><EmergenciesPage /></RequireAuth>} />
      <Route path="/warehouse" element={<RequireAuth><WarehousePage /></RequireAuth>} />
      <Route path="/sanitation" element={<RequireAuth><SanitationPage /></RequireAuth>} />
      <Route path="/improvement" element={<RequireAuth><ImprovementPage /></RequireAuth>} />
      <Route path="/inspections" element={<RequireAuth><InspectionsPage /></RequireAuth>} />
      <Route path="/inspections/:stageCode" element={<RequireAuth><InspectionsPage /></RequireAuth>} />
      <Route path="/meters" element={<RequireAuth><MetersPage /></RequireAuth>} />
      <Route path="/vee" element={<RequireAuth><VeePage /></RequireAuth>} />
      <Route path="/consumption" element={<RequireAuth><ConsumptionPage /></RequireAuth>} />
      <Route path="/control" element={<RequireAuth><ControlPage /></RequireAuth>} />
      <Route path="/control/:orderId" element={<RequireAuth><ControlOrderDetailPage /></RequireAuth>} />
      <Route path="/network-balance" element={<RequireAuth><NetworkBalancePage /></RequireAuth>} />
      <Route path="/network-model" element={<RequireAuth><NetworkModelPage /></RequireAuth>} />
      <Route path="/digital-twin" element={<RequireAuth><DigitalTwinPage /></RequireAuth>} />
      <Route path="/maintenance" element={<RequireAuth><MaintenancePage /></RequireAuth>} />
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
