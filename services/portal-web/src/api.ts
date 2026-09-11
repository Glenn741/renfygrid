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

export interface InvalidReading {
  meter_id: string;
  account_number: string;
  channel: string;
  timestamp: string;
  value: number;
  vee_rule_id: string | null;
  validation_notes: string | null;
}

export function getInvalidReadings(): Promise<InvalidReading[]> {
  return request("/vee/invalid-readings");
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

export function approveControlOrder(
  orderId: string,
  body: { approver_name: string; approver_role: string },
): Promise<{ order_id: string; status: string }> {
  return request(`/control-orders/${orderId}/approve`, { method: "POST", body: JSON.stringify(body) });
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

export { ApiError };
