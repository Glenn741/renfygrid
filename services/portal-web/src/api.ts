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

// --- HES / Ingesta -- eventos/alarmas + cola de reintentos (Sprint C11-4):
// F05 (alarmas reales via push DLMS) y F09 (auditoria de comunicacion) ya
// escribian en meter_event; F08 (cola de reintentos, Sprint C11) ya
// escribia en poller_retry_queue -- nada de esto se veia en el Portal.

export interface HesEventSummary {
  alarms_24h: number;
  critical_alarms_24h: number;
  comm_failures_24h: number;
  comm_success_rate_24h: number | null;
  meters_in_retry_queue: number;
}

export function getHesEventSummary(): Promise<HesEventSummary> {
  return request("/meters/event-summary");
}

export interface MeterEvent {
  meter_id: string;
  account_number: string;
  brand: string | null;
  model: string | null;
  gateway_name: string | null;
  type: string;
  severity: string;
  detail: Record<string, unknown>;
  timestamp: string;
}

export function getMeterEvents(eventType?: string): Promise<MeterEvent[]> {
  return request(`/meters/events${eventType ? `?event_type=${eventType}` : ""}`);
}

export interface RetryQueueRow {
  meter_id: string;
  account_number: string;
  brand: string | null;
  model: string | null;
  failure_count: number;
  next_retry_at: string;
  last_error: string | null;
  updated_at: string;
}

export function getRetryQueue(): Promise<RetryQueueRow[]> {
  return request("/meters/retry-queue");
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

// --- Panel real de Gestion de Consumos (Sprint C11-6): F21-F24 ya estaban
// construidos, pero la pantalla solo mostraba la cola de "under_review" --
// sin resumen, sin las ordenes de relectura/inspeccion visibles (F23), y
// sin forma de cerrar una anomalia investigada (anomaly_status='resolved'
// existia en el esquema desde Sprint 0, nunca se escribia).

export interface ConsumptionSummary {
  total_processed: number;
  by_status: Record<string, number>;
  orders_by_action: Record<string, number>;
  anomaly_rate_pct: number | null;
  billing_ready_pct: number | null;
}

export function getConsumptionSummary(): Promise<ConsumptionSummary> {
  return request("/consumption/summary");
}

export interface ConsumptionOrder {
  meter_id: string;
  account_number: string;
  action: string;
  timestamp: string;
  period: string;
  value: number;
  anomaly_status: string;
}

export function getConsumptionOrders(): Promise<ConsumptionOrder[]> {
  return request("/consumption/orders");
}

export function resolveConsumptionAnomaly(body: {
  meter_id: string;
  period_start: string;
  period_end: string;
  notes: string;
}) {
  return request<{ status: string }>("/consumption/resolve", { method: "POST", body: JSON.stringify(body) });
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
  meter_protected: boolean;
}

export function getControlOrders(status?: string): Promise<ControlOrder[]> {
  return request(`/control-orders${status ? `?status=${status}` : ""}`);
}

export function approveControlOrder(orderId: string): Promise<{ order_id: string; status: string }> {
  // Sprint C5: quien aprueba sale del JWT del que hace la llamada, no de un
  // campo de texto libre -- ver services/portal-api/auth_dependency.py.
  return request(`/control-orders/${orderId}/approve`, { method: "POST", body: "{}" });
}

// --- Panel real de Control/SCR (Sprint C11-5): "command success rates, or
// retry backlog" es justo el tipo de KPI que un CIS/MDM de referencia
// expone -- antes solo existia la cola de pendientes, sin historial ni
// tasa de exito, y ninguna cuenta protegida contra suspension/desconexion
// (Ley 142 + normas CRA/CREG en Colombia).

export interface ControlSummary {
  total_orders: number;
  by_type: Record<string, number>;
  by_status: Record<string, number>;
  pending_approval: number;
  command_success_rate_pct: number | null;
}

export function getControlSummary(): Promise<ControlSummary> {
  return request("/control-orders/summary");
}

export interface ProtectedMeter {
  meter_id: string;
  account_number: string;
  brand: string | null;
  model: string | null;
  reason: string | null;
  marked_by: string | null;
  marked_at: string | null;
}

export function getProtectedMeters(): Promise<ProtectedMeter[]> {
  return request("/meters/protected");
}

export function markMeterProtection(meterId: string, body: { protected: boolean; reason?: string | null }) {
  return request<{ meter_id: string; protected: boolean }>(`/meters/${meterId}/protection`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function bulkMarkMeterProtection(body: { account_numbers: string[]; reason: string }) {
  return request<{ marked: string[]; not_found: string[] }>("/meters/protection/bulk", {
    method: "POST",
    body: JSON.stringify(body),
  });
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

// --- Track B: Balance de Red (Sprint B1/B1-2) -- matriz de Balance Hidrico
// IWA completa (docs/07-track-b-alcance-funcional.md SS1); NRW/ILI se
// calculan en el backend al ingestar, nunca en el navegador.

export interface NetworkZone {
  zone_id: string;
  name: string;
  type: string;
  data_source: string;
  parent_zone_id: string | null;
  network_length_km: number | null;
  num_connections: number | null;
  avg_pressure_mca: number | null;
  avg_service_connection_length_km: number | null;
  nrw_threshold_pct: number | null;
  centroid_lat: number | null;
  centroid_lon: number | null;
}

export function getNetworkZones(): Promise<NetworkZone[]> {
  return request("/network-zones");
}

export function createNetworkZone(body: {
  name: string;
  type: string;
  data_source?: string;
  parent_zone_id?: string | null;
  network_length_km?: number | null;
  num_connections?: number | null;
  avg_pressure_mca?: number | null;
  avg_service_connection_length_km?: number | null;
  nrw_threshold_pct?: number | null;
  centroid_lat?: number | null;
  centroid_lon?: number | null;
}): Promise<{ zone_id: string }> {
  return request("/network-zones", { method: "POST", body: JSON.stringify(body) });
}

export interface NetworkBalance {
  balance_id: string;
  zone_id: string;
  zone_name: string;
  period: string;
  method: string;
  system_input_volume: number;
  billed_metered_consumption: number;
  billed_unbilled_consumption: number;
  unbilled_authorized_consumption: number;
  apparent_losses: number;
  real_losses: number;
  nrw: number | null;
  nrw_pct: number | null;
  ili: number | null;
  balance_check_pct: number | null;
  exceeds_threshold: boolean | null;
  version: number;
  calculated_at: string;
}

export function getNetworkBalances(zoneId?: string): Promise<NetworkBalance[]> {
  return request(`/network-balances${zoneId ? `?zone_id=${zoneId}` : ""}`);
}

export function submitNetworkBalance(
  zoneId: string,
  body: {
    period_start: string;
    period_end: string;
    method: string;
    system_input_volume: number;
    billed_metered_consumption?: number;
    billed_unbilled_consumption?: number;
    unbilled_authorized_consumption?: number;
    apparent_losses?: number;
    real_losses?: number;
  },
): Promise<NetworkBalance> {
  return request(`/network-zones/${zoneId}/balance`, { method: "POST", body: JSON.stringify(body) });
}

export interface NetworkBalanceSummary {
  total_zones: number;
  zones_with_balance: number;
  avg_nrw_pct: number | null;
  worst_ili: number | null;
  zones_exceeding_threshold: number;
}

export function getNetworkBalanceSummary(): Promise<NetworkBalanceSummary> {
  return request("/network-balances/summary");
}

// --- Track B: Modelado Hidraulico (Sprint B3) -- carga/versionado de un
// modelo EPANET (.inp) real y simulacion via WNTR (motor EPANET 2.2, el
// mismo que usan Bentley WaterGEMS/Innovyze InfoWater por debajo).

export interface NetworkModel {
  model_id: string;
  name: string;
  format: string;
  version: number;
  valid_from: string;
  zone_id: string | null;
}

export function getNetworkModels(): Promise<NetworkModel[]> {
  return request("/network-models");
}

export function createNetworkModel(body: { name: string; inp_content: string; zone_id?: string | null }): Promise<NetworkModel> {
  return request("/network-models", { method: "POST", body: JSON.stringify(body) });
}

export interface NodeSimStats {
  min_pressure: number;
  max_pressure: number;
  avg_pressure: number;
}

export interface LinkSimStats {
  min_flowrate: number;
  max_flowrate: number;
  avg_flowrate: number;
}

export interface SimulationResult {
  simulation_id: string;
  model_id: string;
  scenario: string;
  calculated_at: string;
  duration_hours: number;
  num_nodes: number;
  num_links: number;
  nodes: Record<string, NodeSimStats>;
  links: Record<string, LinkSimStats>;
  calibrated?: boolean;
  target_leak_lps?: number;
  node_leak_lps?: Record<string, number>;
  skipped_nodes?: string[];
  real_losses_m3?: number;
  period_days?: number;
}

export function simulateNetworkModel(modelId: string, scenario: string, calibrate = false): Promise<SimulationResult> {
  return request(`/network-models/${modelId}/simulate`, { method: "POST", body: JSON.stringify({ scenario, calibrate }) });
}

export function getNetworkModelSimulations(modelId: string): Promise<SimulationResult[]> {
  return request(`/network-models/${modelId}/simulations`);
}

// --- Modulo de georreferenciacion (docs/07-track-b-alcance-funcional.md SS7) ---

export function getNetworkModelGeojson(modelId: string): Promise<GeoJSON.FeatureCollection> {
  return request(`/network-models/${modelId}/geojson`);
}

export function getNetworkZonesGeojson(): Promise<GeoJSON.FeatureCollection> {
  return request("/network-zones/geojson");
}

// --- Track B, Sprint B5: Gemelo Digital (inventario de activos + conectividad) ---

export interface NetworkAssetConnection {
  source_asset_id: string;
  target_asset_id: string;
  connection_type: string;
}

export interface NetworkAsset {
  asset_id: string;
  zone_id: string | null;
  type: string;
  attributes: Record<string, unknown>;
  geometry: { type: string; coordinates: number[] } | null;
  status: string;
  version: number;
  valid_from: string;
}

export interface NetworkAssetDetail extends NetworkAsset {
  connectivity: NetworkAssetConnection[];
}

export function getNetworkAssets(params?: { zone_id?: string; asset_type?: string }): Promise<NetworkAsset[]> {
  const q = new URLSearchParams();
  if (params?.zone_id) q.set("zone_id", params.zone_id);
  if (params?.asset_type) q.set("asset_type", params.asset_type);
  const qs = q.toString();
  return request(`/network-assets${qs ? `?${qs}` : ""}`);
}

export function getNetworkAssetDetail(assetId: string): Promise<NetworkAssetDetail> {
  return request(`/network-assets/${assetId}`);
}

export function createNetworkAsset(body: {
  type: string;
  zone_id?: string | null;
  attributes?: Record<string, unknown>;
  geometry?: { type: string; coordinates: number[] } | null;
  status?: string;
}): Promise<{ asset_id: string }> {
  return request("/network-assets", { method: "POST", body: JSON.stringify(body) });
}

export function updateNetworkAssetStatus(assetId: string, status: string): Promise<{ asset_id: string; status: string; version: number }> {
  return request(`/network-assets/${assetId}/status`, { method: "PATCH", body: JSON.stringify({ status }) });
}

export function connectNetworkAssets(body: {
  source_asset_id: string;
  target_asset_id: string;
  connection_type: string;
}): Promise<NetworkAssetConnection> {
  return request("/asset-connectivity", { method: "POST", body: JSON.stringify(body) });
}

export function getNetworkAssetsGeojson(): Promise<GeoJSON.FeatureCollection> {
  return request("/network-assets/geojson");
}

// --- Track B, Sprint B6: generar un modelo EPANET desde el Gemelo Digital ---

export function generateNetworkModelFromTwin(zoneId: string, name: string): Promise<NetworkModel> {
  return request(`/network-zones/${zoneId}/generate-model`, { method: "POST", body: JSON.stringify({ name }) });
}

// --- Track B, Sprint B7: Gestion de Mantenimiento + integracion BayForce ---

export interface MaintenanceOrder {
  order_id: string;
  asset_id: string;
  type: string;
  source: string;
  status: string;
  bayforce_order_ref: string | null;
  reason: string | null;
  created_at: string;
}

export function getMaintenanceOrders(params?: { status?: string; asset_id?: string }): Promise<MaintenanceOrder[]> {
  const q = new URLSearchParams();
  if (params?.status) q.set("status", params.status);
  if (params?.asset_id) q.set("asset_id", params.asset_id);
  const qs = q.toString();
  return request(`/maintenance-orders${qs ? `?${qs}` : ""}`);
}

export function createMaintenanceOrder(body: {
  asset_id: string;
  type: string;
  source: string;
  reason?: string | null;
}): Promise<MaintenanceOrder> {
  return request("/maintenance-orders", { method: "POST", body: JSON.stringify(body) });
}

export function sendMaintenanceOrderToBayforce(orderId: string): Promise<{ order_id: string; status: string; bayforce_order_ref: string }> {
  return request(`/maintenance-orders/${orderId}/send-to-bayforce`, { method: "POST", body: "{}" });
}

export { ApiError };
