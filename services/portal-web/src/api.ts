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

export { ApiError };
