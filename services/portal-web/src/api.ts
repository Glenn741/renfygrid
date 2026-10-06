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
    // sesion vencida (el JWT dura lo que la organizacion definio en
    // Configuracion -> Sesion, tenant.config.session_ttl_seconds) -- antes
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
  hes: { meters_total: number; meters_stale: number | null };
  vee: { invalid_pending: number };
  consumption: { under_review: number };
  control: { pending_approval: number };
  network_balance: { zones_exceeding_threshold: number };
  digital_twin: { assets_out_of_service: number };
  maintenance: { orders_pending: number };
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
  // null = sin umbral configurado todavia (Configuración → HES), no "sano" ni "caído".
  is_stale: boolean | null;
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

// Sin default fijo (2026-09-15, a pedido explícito del usuario): sin
// argumento, el backend resuelve el umbral REAL configurado por el tenant
// (`GET/PUT /settings/hes`) -- nunca un 3600 adivinado en el frontend.
export function getIngestionMetrics(staleAfterSeconds?: number): Promise<IngestionMetrics> {
  const qs = staleAfterSeconds !== undefined ? `?stale_after_seconds=${staleAfterSeconds}` : "";
  return request(`/observability/ingestion${qs}`);
}

export interface HesSettings {
  stale_after_seconds: number | null;
}

export function getHesSettings(): Promise<HesSettings> {
  return request("/settings/hes");
}

export function setHesSettings(staleAfterSeconds: number): Promise<HesSettings> {
  return request("/settings/hes", { method: "PUT", body: JSON.stringify({ stale_after_seconds: staleAfterSeconds }) });
}

// --- HES / Ingesta -- flota por marca y capa de agregacion (Sprint C7/C8) ---

export interface FleetSummaryRow {
  brand: string;
  model: string | null;
  total: number;
  active: number;
  reporting: number | null;
  reporting_pct: number | null;
}

export function getFleetSummary(): Promise<FleetSummaryRow[]> {
  return request("/meters/fleet-summary");
}

// --- Mapa de medidores + distribución estadística + sectores hidráulicos
// (macro/micro medición, 2026-09-15) ---

export function getMetersGeojson(): Promise<GeoJSON.FeatureCollection> {
  return request("/meters/geojson");
}

export interface ConsumptionDistribution {
  window_days: number;
  meters_with_data: number;
  avg_m3: number | null;
  min_m3: number | null;
  max_m3: number | null;
  buckets: { label: string; count: number }[];
}

export function getConsumptionDistribution(): Promise<ConsumptionDistribution> {
  return request("/meters/consumption-distribution");
}

export interface ExceptionRateByBrand {
  brand: string;
  total_processed: number;
  invalid_count: number;
  exception_rate_pct: number | null;
}

export function getExceptionRateByBrand(): Promise<ExceptionRateByBrand[]> {
  return request("/meters/exception-rate-by-brand");
}

export interface SectorSummary {
  zone_id: string;
  zone_name: string;
  macro_meter_id: string | null;
  micro_count: number;
  micro_with_data: number;
  macro_volume_m3: number | null;
  micro_total_m3: number | null;
  nrw_pct: number | null;
  window: string;
}

export function getSectorSummary(): Promise<SectorSummary[]> {
  return request("/meters/sector-summary");
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
  real_losses_derived: boolean;
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

// --- Track B, Sprint B7 + CMMS real (2026-09-14): Gestion de Mantenimiento ---

export interface MaintenanceOrder {
  order_id: string;
  asset_id: string;
  type: string;
  source: string;
  priority: string | null;
  status: string;
  bayforce_order_ref: string | null;
  reason: string | null;
  created_at: string;
  sla_due_at: string | null;
  failure_code_id: string | null;
  scheduled_at: string | null;
  assigned_crew_id: string | null;
  labor_hours: number | null;
  materials_used: string | null;
  root_cause: string | null;
  closed_at: string | null;
  is_overdue: boolean;
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
  priority: string;
  reason?: string | null;
}): Promise<MaintenanceOrder> {
  return request("/maintenance-orders", { method: "POST", body: JSON.stringify(body) });
}

export function sendMaintenanceOrderToBayforce(orderId: string): Promise<{ order_id: string; status: string; bayforce_order_ref: string }> {
  return request(`/maintenance-orders/${orderId}/send-to-bayforce`, { method: "POST", body: "{}" });
}

export function scheduleMaintenanceOrder(orderId: string, scheduledAt: string): Promise<MaintenanceOrder> {
  return request(`/maintenance-orders/${orderId}/schedule`, { method: "POST", body: JSON.stringify({ scheduled_at: scheduledAt }) });
}

export function assignMaintenanceOrder(orderId: string, crewId: string): Promise<MaintenanceOrder> {
  return request(`/maintenance-orders/${orderId}/assign`, { method: "POST", body: JSON.stringify({ crew_id: crewId }) });
}

export function startMaintenanceOrder(orderId: string): Promise<MaintenanceOrder> {
  return request(`/maintenance-orders/${orderId}/start`, { method: "POST", body: "{}" });
}

export function closeMaintenanceOrder(orderId: string, body: {
  status: "completed" | "cancelled";
  labor_hours?: number | null;
  materials_used?: string | null;
  root_cause?: string | null;
  failure_code_id?: string | null;
}): Promise<MaintenanceOrder> {
  return request(`/maintenance-orders/${orderId}/close`, { method: "POST", body: JSON.stringify(body) });
}

export interface MaintenanceKpis {
  total_orders: number;
  mttr_hours: number | null;
  backlog: { count: number; avg_age_hours: number | null };
  pm_compliance_pct: number | null;
  overdue_count: number;
  by_status: Record<string, number>;
  by_priority: Record<string, number>;
}

export function getMaintenanceKpis(): Promise<MaintenanceKpis> {
  return request("/maintenance/kpis");
}

export interface SlaPolicy {
  priority: string;
  target_hours: number;
}

export function getSlaPolicies(): Promise<SlaPolicy[]> {
  return request("/maintenance/sla-policies");
}

export function setSlaPolicy(priority: string, targetHours: number): Promise<SlaPolicy> {
  return request("/maintenance/sla-policies", { method: "POST", body: JSON.stringify({ priority, target_hours: targetHours }) });
}

export interface FailureCode {
  failure_code_id: string;
  code: string;
  label: string;
  is_active: boolean;
}

export function getFailureCodes(includeInactive = false): Promise<FailureCode[]> {
  return request(`/maintenance/failure-codes${includeInactive ? "?include_inactive=true" : ""}`);
}

export function createFailureCode(code: string, label: string): Promise<FailureCode> {
  return request("/maintenance/failure-codes", { method: "POST", body: JSON.stringify({ code, label }) });
}

export function deactivateFailureCode(failureCodeId: string): Promise<void> {
  return request(`/maintenance/failure-codes/${failureCodeId}`, { method: "DELETE" });
}

export interface Crew {
  crew_id: string;
  name: string;
  is_active: boolean;
}

export function getCrews(includeInactive = false): Promise<Crew[]> {
  return request(`/maintenance/crews${includeInactive ? "?include_inactive=true" : ""}`);
}

export function createCrew(name: string): Promise<Crew> {
  return request("/maintenance/crews", { method: "POST", body: JSON.stringify({ name }) });
}

export function deactivateCrew(crewId: string): Promise<void> {
  return request(`/maintenance/crews/${crewId}`, { method: "DELETE" });
}

export interface PmPlan {
  pm_plan_id: string;
  asset_id: string;
  order_type: string;
  priority: string;
  interval_days: number;
  next_due_at: string;
  last_generated_at: string | null;
  is_active: boolean;
}

export function getPmPlans(): Promise<PmPlan[]> {
  return request("/maintenance/pm-plans");
}

export function createPmPlan(body: {
  asset_id: string;
  order_type: string;
  priority: string;
  interval_days: number;
  next_due_at: string;
}): Promise<PmPlan> {
  return request("/maintenance/pm-plans", { method: "POST", body: JSON.stringify(body) });
}

export function generateDuePmOrders(): Promise<MaintenanceOrder[]> {
  return request("/maintenance/pm-plans/generate-due", { method: "POST", body: "{}" });
}

export interface SessionInfo {
  tenant_id: string;
  tenant_name: string | null;
  email: string;
  role: string | null;
  issued_at: string | null;
  expires_at: string;
}

export function getSession(): Promise<SessionInfo> {
  return request("/auth/me");
}

export function getSessionSettings(): Promise<{ session_ttl_seconds: number | null }> {
  return request("/settings/session");
}

export function setSessionSettings(sessionTtlSeconds: number): Promise<{ session_ttl_seconds: number | null }> {
  return request("/settings/session", { method: "PUT", body: JSON.stringify({ session_ttl_seconds: sessionTtlSeconds }) });
}

// ── Track D, Sprint D0 -- motor de paquetes (docs/04-plan-sprints.md SS11.4) ──

export interface Pack {
  pack_id: string;
  kind: "core" | "regulatory" | "program";
  country: string | null;
  name: string;
  version: string;
  source_note: string;
}

export function getPacks(): Promise<{ packs: Pack[]; active: string[] }> {
  return request("/packs");
}

export function adoptPack(packId: string): Promise<{ pack_id: string; active_packs: string[] }> {
  return request(`/packs/${encodeURIComponent(packId)}/adopt`, { method: "POST", body: "{}" });
}

export interface ComponentType {
  code: string;
  pack_id: string;
  service: "water" | "sanitation" | "support";
  stage_order: number | null;
  is_treatment_stage: boolean;
  label: string;
  description: string | null;
}

export function getComponentTypes(): Promise<ComponentType[]> {
  return request("/component-types");
}

export interface RuleBand {
  upper: number | null;
  upper_inclusive?: boolean;
  code: string;
  label: string;
  severity: "ok" | "alert" | "critical";
}

export interface ParameterRule {
  rule_id: string;
  pack_id: string;
  bands: RuleBand[];
  citation: string;
  parameter: { code: string; label: string; unit: string; measured_by: "field" | "lab" };
}

export function getParameterRules(): Promise<ParameterRule[]> {
  return request("/parameter-rules");
}

export interface ScaleEntry {
  code: string;
  label: string;
  finding: boolean;
  finding_priority?: string;
  score: number;
}

export interface ChecklistTemplate {
  id: string;
  pack_id: string;
  kind: "inspection" | "traffic_light" | "self_assessment";
  title: string;
  purpose: string;
  scale: ScaleEntry[];
  items: { key: string; text: string; component_service?: string }[];
}

export function getChecklistTemplates(): Promise<ChecklistTemplate[]> {
  return request("/checklist-templates");
}

export interface ChecklistAnswerInput {
  item_key: string;
  answer_code: string;
  observation?: string | null;
  action?: string | null;
  responsible?: string | null;
  due_date?: string | null;
  asset_id?: string | null;
}

export interface Score {
  score: number;
  max_score: number;
  pct: number | null;
}

export function submitChecklistRun(body: {
  template_id: string;
  answers: ChecklistAnswerInput[];
  notes?: string | null;
}): Promise<{ run_id: string; template_id: string; performed_at: string; score: Score; findings_created: string[] }> {
  return request("/checklist-runs", { method: "POST", body: JSON.stringify(body) });
}

export interface ChecklistRunSummary {
  run_id: string;
  template_id: string;
  performed_at: string;
  performed_by: string;
  notes: string | null;
  answer_count: number;
}

export function getChecklistRuns(templateId?: string): Promise<ChecklistRunSummary[]> {
  return request(`/checklist-runs${templateId ? `?template_id=${encodeURIComponent(templateId)}` : ""}`);
}

export interface ChecklistRunDetail {
  run_id: string;
  template_id: string;
  title: string;
  kind: ChecklistTemplate["kind"];
  performed_at: string;
  performed_by: string;
  notes: string | null;
  answers: {
    item_key: string;
    text: string;
    answer_code: string;
    answer_label: string;
    observation: string | null;
    action: string | null;
    responsible: string | null;
    due_date: string | null;
  }[];
  score: Score;
}

export function getChecklistRun(runId: string): Promise<ChecklistRunDetail> {
  return request(`/checklist-runs/${runId}`);
}

export interface Finding {
  finding_id: string;
  source_kind: "critical_point" | "checklist" | "reading" | "manual";
  source_ref: string | null;
  asset_id: string | null;
  location_text: string | null;
  geometry: unknown;
  description: string;
  priority: "high" | "medium" | "low";
  support_level: "community" | "local_government" | "specialized" | null;
  status: "open" | "in_progress" | "closed";
  to_improvement_plan: boolean;
  created_by: string;
  created_at: string;
  closed_at: string | null;
}

export function getFindings(status?: string): Promise<Finding[]> {
  return request(`/findings${status ? `?status=${status}` : ""}`);
}

export function createFinding(body: {
  description: string;
  priority: string;
  source_kind?: string;
  asset_id?: string | null;
  location_text?: string | null;
  support_level?: string | null;
}): Promise<{ finding_id: string }> {
  return request("/findings", { method: "POST", body: JSON.stringify(body) });
}

export function updateFinding(findingId: string, body: {
  status?: string;
  priority?: string;
  support_level?: string;
  to_improvement_plan?: boolean;
}): Promise<Finding> {
  return request(`/findings/${findingId}`, { method: "PATCH", body: JSON.stringify(body) });
}

export interface RouteStage {
  type: string;
  label: string;
  stage_order: number | null;
  assets: { asset_id: string; type: string; status: string; attributes: Record<string, unknown>; zone_id: string | null }[];
}

export function getSystemRoute(): Promise<{ services: Record<string, RouteStage[]>; accessories: RouteStage[] }> {
  return request("/reports/system-route");
}

export interface TreatmentStageRow {
  type: string;
  label: string;
  exists: boolean;
  works: boolean | null;
  asset_count: number;
  open_findings: { finding_id: string; description: string; priority: string }[];
}

export function getTreatmentTrain(): Promise<TreatmentStageRow[]> {
  return request("/reports/treatment-train");
}

export function getTrafficLight(): Promise<{ run: ChecklistRunDetail | null }> {
  return request("/reports/traffic-light");
}

export function getInstrumentation(): Promise<{ levels: Record<string, string> }> {
  return request("/settings/instrumentation");
}

export function setInstrumentation(levels: Record<string, string>): Promise<{ levels: Record<string, string> }> {
  return request("/settings/instrumentation", { method: "PUT", body: JSON.stringify({ levels }) });
}

export { ApiError };
