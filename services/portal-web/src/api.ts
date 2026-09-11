// Cliente del Portal/API (Sprint 8-10) -- sin libreria de fetch aparte,
// alcanza con fetch nativo + TanStack Query para el cacheo/estado.

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

const TOKEN_KEY = "renfygrid_token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string> | undefined),
  };
  if (token) headers.Authorization = `Bearer ${token}`;

  const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (!response.ok) {
    // Un 401 en cualquier endpoint que NO sea el login mismo significa
    // sesion vencida (el JWT dura 1h, ver renmeter_common/auth.py) -- antes
    // se quedaba en la pantalla con las llamadas fallando en silencio
    // (visto en vivo: 401 repetido en consola sin que el usuario supiera
    // por que). Limpiar el token y mandar a /login en vez de dejarlo ahi.
    if (response.status === 401 && path !== "/auth/login" && !window.location.pathname.startsWith("/login")) {
      clearToken();
      window.location.href = "/login";
    }
    const body = await response.json().catch(() => ({}));
    throw new ApiError(response.status, body.detail ?? `Error ${response.status}`);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export interface LoginRequest {
  tenant_id: string;
  email: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
}

export function login(body: LoginRequest): Promise<LoginResponse> {
  return request("/auth/login", { method: "POST", body: JSON.stringify(body) });
}

export interface DashboardOverview {
  hes: { meters_total: number; meters_stale: number };
  vee: { invalid_pending: number };
  consumption: { under_review: number };
  control: { pending_approval: number };
}

export function getDashboardOverview(): Promise<DashboardOverview> {
  return request("/dashboard/overview");
}

// --- Nivel 2 (Sprint C2): un endpoint por etapa, cada uno YA filtrado del
// lado del servidor a lo que hay que atender -- el patron exception-first
// no es un filtro de UI, es como estan escritos los endpoints. ---

export interface MeterIngestion {
  meter_id: string;
  account_number: string;
  brand: string | null;
  model: string | null;
  gateway_name: string | null;
  readings_24h: number;
  last_reading_at: string | null;
  communication_failures_24h: number;
  is_stale: boolean;
}

export interface IngestionAlert {
  meter_id: string;
  account_number: string;
  type: string;
  detail: string;
}

export interface IngestionMetrics {
  meters: MeterIngestion[];
  alerts: IngestionAlert[];
}

export function getIngestionMetrics(staleAfterSeconds = 3600): Promise<IngestionMetrics> {
  return request(`/observability/ingestion?stale_after_seconds=${staleAfterSeconds}`);
}

// --- HES / Ingesta -- flota por marca y capa de agregacion (Sprint C7/C8) ---

export interface FleetSummaryRow {
  brand: string;
  model: string | null;
  total: number;
  active: number;
  reporting: number;
  reporting_pct: number;
}

export function getFleetSummary(): Promise<FleetSummaryRow[]> {
  return request("/meters/fleet-summary");
}

export interface Gateway {
  gateway_id: string;
  name: string;
  host: string | null;
  port: number | null;
  meter_count: number;
  brands: string[];
  last_poll_at: string | null;
  success_rate_24h: number | null;
}

export function getGateways(): Promise<Gateway[]> {
  return request("/gateways");
}

export interface InvalidReading {
  meter_id: string;
  account_number: string;
  channel: string;
  timestamp: string;
  value: number;
  vee_rule_id: string | null;
  validation_notes: string | null;
  rule_type: string | null;
}

export function getInvalidReadings(): Promise<InvalidReading[]> {
  return request("/vee/invalid-readings");
}

// --- Panel real de VEE, por etapa (Sprint C11-3): F14-F19 ya estaban
// construidos, pero el panel no separaba Validacion/Estimacion/Edicion
// como 3 niveles de procesamiento con sus propios KPIs -- mismo criterio
// que Oracle Utilities MDM (dashboard "VEE Exceptions": Overview/Trend) o
// Itron Enterprise Edition (validation sets vs. estimation sets vs. cola
// de excepciones separadas).

export interface VeeValidationSummary {
  total_processed: number;
  invalid_total: number;
  exception_rate_pct: number | null;
  invalid_by_type: Record<string, number>;
  active_rules_by_type: Record<string, number>;
  active_rules_total: number;
  trend_7d: { date: string; total: number; invalid: number }[];
}

export interface VeeEstimationSummary {
  total_estimated: number;
  estimated_24h: number;
  fill_rate_pct: number | null;
  by_method: Record<string, number>;
  active_rules_total: number;
}

export interface VeeEditingSummary {
  total_edits: number;
  edits_24h: number;
  top_editors: { user_name: string; count: number }[];
}

export interface VeeSummary {
  validation: VeeValidationSummary;
  estimation: VeeEstimationSummary;
  editing: VeeEditingSummary;
}

export function getVeeSummary(): Promise<VeeSummary> {
  return request("/vee/summary");
}

export interface EstimatedReading {
  meter_id: string;
  account_number: string;
  channel: string;
  timestamp: string;
  value: number;
  created_at: string;
  estimation_method: string | null;
}

export function getEstimatedReadings(): Promise<EstimatedReading[]> {
  return request("/vee/estimated-readings");
}

export interface VeeEdit {
  meter_id: string;
  account_number: string;
  channel: string;
  timestamp: string;
  previous_value: number;
  new_value: number;
  user_name: string;
  justification: string;
  edited_at: string;
}

export function getVeeEdits(): Promise<VeeEdit[]> {
  return request("/vee/edits");
}

export interface Consumption {
  meter_id: string;
  account_number: string;
  period: string;
  value: number;
  anomaly_status: string;
  created_at: string;
}

export function getConsumptionUnderReview(): Promise<Consumption[]> {
  return request("/consumption?anomaly_status=under_review");
}

export interface ControlOrder {
  order_id: string;
  meter_id: string;
  account_number: string;
  type: string;
  status: string;
  requested_by: string;
  justification: string | null;
  requested_at: string | null;
  approved_by: string | null;
  approved_at: string | null;
}

export function getControlOrders(status?: string): Promise<ControlOrder[]> {
  return request(`/control-orders${status ? `?status=${status}` : ""}`);
}

export function approveControlOrder(orderId: string): Promise<{ order_id: string; status: string }> {
  // Sprint C5: quien aprueba sale del JWT del que hace la llamada, no de un
  // campo de texto libre -- ver services/portal-api/auth_dependency.py.
  return request(`/control-orders/${orderId}/approve`, { method: "POST", body: "{}" });
}

// --- Configuración: editor de reglas (F50, Sprint C3) ---

export interface VeeRule {
  id: string;
  type: string;
  params: Record<string, unknown>;
  priority: number;
  is_active: boolean;
  valid_from: string | null;
  valid_to: string | null;
}

export function getVeeRules(): Promise<VeeRule[]> {
  return request("/vee-rules");
}

export function createVeeRule(body: { type: string; params: Record<string, unknown>; priority: number }) {
  return request<{ id: string }>("/vee-rules", { method: "POST", body: JSON.stringify(body) });
}

export function deactivateVeeRule(id: string) {
  return request<{ id: string }>(`/vee-rules/${id}`, { method: "PATCH" });
}

// --- Integraciones / Service Orders (Sprint C6, sobre el endpoint de C5) ---

export interface ServiceOrder {
  kind: "control_order" | "on_demand_read" | "ping";
  id: string;
  type: string;
  meter_id: string;
  account_number: string;
  status: string;
  requested_by: string | null;
  origin: string;
  mode: "automatico" | "manual";
  timestamp: string | null;
}

export function getServiceOrders(): Promise<ServiceOrder[]> {
  return request("/integrations/service-orders");
}

export interface ConsumptionAnomalyRule {
  id: string;
  condition: Record<string, unknown>;
  action: string;
  is_active: boolean;
}

export function getConsumptionAnomalyRules(): Promise<ConsumptionAnomalyRule[]> {
  return request("/consumption-anomaly-rules");
}

export function createConsumptionAnomalyRule(body: { condition: Record<string, unknown>; action: string }) {
  return request<{ id: string }>("/consumption-anomaly-rules", { method: "POST", body: JSON.stringify(body) });
}

export function deactivateConsumptionAnomalyRule(id: string) {
  return request<{ id: string }>(`/consumption-anomaly-rules/${id}`, { method: "PATCH" });
}

export interface ApprovalLevel {
  id: string;
  order_type: string;
  requires_human_approval: boolean;
  min_required_role: string;
}

export function getApprovalLevels(): Promise<ApprovalLevel[]> {
  return request("/control-approval-levels");
}

export function createApprovalLevel(body: {
  order_type: string;
  requires_human_approval: boolean;
  min_required_role: string;
}) {
  return request<{ id: string }>("/control-approval-levels", { method: "POST", body: JSON.stringify(body) });
}

// --- Editor de mapeo OBIS (F50/E19, Sprint C10) -- mismo patron de "crear
// version nueva reemplaza la anterior" que ApprovalLevel, sobre meter_protocol. ---

export interface ObisChannelMapping {
  obis_code: string;
  attribute_index: number;
}

export interface ProtocolMapping {
  id: string;
  brand: string;
  model: string;
  protocol: string;
  obis_mapping: Record<string, ObisChannelMapping>;
  security_mode: string | null;
  version: number;
  valid_from: string | null;
  valid_to: string | null;
}

export function getProtocolMappings(): Promise<ProtocolMapping[]> {
  return request("/obis-mappings");
}

export function createProtocolMapping(body: {
  brand: string;
  model: string;
  protocol: string;
  obis_mapping: Record<string, ObisChannelMapping>;
  security_mode?: string | null;
}) {
  return request<{ id: string }>("/obis-mappings", { method: "POST", body: JSON.stringify(body) });
}

// --- Nivel 3: detalle y acciones (F51, Sprint C4) ---

export function editReading(body: {
  meter_id: string;
  channel: string;
  timestamp: string;
  new_value: number;
  user_name: string;
  justification: string;
}) {
  return request<{ status: string }>("/vee/invalid-readings/edit", { method: "POST", body: JSON.stringify(body) });
}

export function readMeterNow(meterId: string, channel: string) {
  return request<{ meter_id: string; timestamp: string; channel: string; value: number }>(
    `/meters/${meterId}/reads`,
    { method: "POST", body: JSON.stringify({ channel }) },
  );
}

export interface ControlOrderAudit {
  previous_status: string | null;
  new_status: string;
  actor: string;
  timestamp: string;
  detail: Record<string, unknown> | null;
}

export interface ControlOrderDetail extends ControlOrder {
  confirmed_at: string | null;
  audit: ControlOrderAudit[];
}

export function getControlOrderDetail(orderId: string): Promise<ControlOrderDetail> {
  return request(`/control-orders/${orderId}`);
}

export { ApiError };
