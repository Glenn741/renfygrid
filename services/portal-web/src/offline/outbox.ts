// Cola de envios sin conexion de la app del operador (Track D, D1.3).
//
// Lo que el operador registra (mediciones 7B y tomas de la bitacora 7C) se
// guarda primero aqui, en IndexedDB, con un `client_id` generado en el
// dispositivo. Al sincronizar se envian en orden: primero las mediciones y
// despues las tomas, que pueden apuntar a una medicion hecha sin conexion
// (`reading_client_id` -> `reading_id` del servidor). La API es idempotente
// por `client_id` (migracion 0030): reenviar lo mismo devuelve lo ya guardado,
// asi que un corte a mitad de la sincronizacion no duplica nada.
//
// Cada elemento lleva el tenant del token con que se registro: en un equipo
// compartido nunca se envia a otra organizacion.

import { ApiError, createOperationLogEntry, getToken, recordFieldReading } from "../api";

const DB_NAME = "renfygrid-operator";
const STORE = "outbox";

export type OutboxStatus = "pending" | "synced" | "failed";

export interface ReadingPayload {
  parameter_code: string;
  value: number;
  sampling_point_id: string | null;
  action_taken: string | null;
  measured_at: string;
}

export interface LogPayload {
  moment_code: string | null;
  tank_level_pct: number | null;
  chlorine_applied: number | null;
  chlorine_applied_unit: "g" | "ml" | null;
  /** Medicion hecha en este dispositivo (se resuelve al sincronizar). */
  reading_client_id: string | null;
  appearance: "clear" | "turbid" | "colored" | null;
  status: "good" | "alert";
  notes: string | null;
  logged_at: string;
}

export interface OutboxItem {
  client_id: string;
  tenant_id: string;
  kind: "reading" | "log";
  payload: ReadingPayload | LogPayload;
  /** Resumen legible para la lista (p. ej. "Cloro 0,2 mg/L en Escuela"). */
  label: string;
  created_at: string;
  status: OutboxStatus;
  server_id: string | null;
  /** Interpretacion del servidor al sincronizar (Bajo/Adecuado/Alto, hallazgo). */
  server_note: string | null;
  error: string | null;
}

export function tokenTenantId(): string | null {
  const token = getToken();
  if (!token) return null;
  try {
    const payload = JSON.parse(atob(token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/")));
    return typeof payload.tenant_id === "string" ? payload.tenant_id : null;
  } catch {
    return null;
  }
}

export function newClientId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID();
  // Respaldo RFC 4122 v4 para navegadores sin randomUUID (la API exige un UUID valido).
  const b = (globalThis.crypto as Crypto).getRandomValues(new Uint8Array(16));
  b[6] = (b[6] & 0x0f) | 0x40;
  b[8] = (b[8] & 0x3f) | 0x80;
  const h = [...b].map((x) => x.toString(16).padStart(2, "0")).join("");
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`;
}

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, 1);
    req.onupgradeneeded = () => {
      const store = req.result.createObjectStore(STORE, { keyPath: "client_id" });
      store.createIndex("tenant_id", "tenant_id");
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function tx<T>(mode: IDBTransactionMode, fn: (store: IDBObjectStore) => IDBRequest<T>): Promise<T> {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const t = db.transaction(STORE, mode);
    const req = fn(t.objectStore(STORE));
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

export async function listOutbox(tenantId: string): Promise<OutboxItem[]> {
  const all = await tx<OutboxItem[]>("readonly", (s) => s.index("tenant_id").getAll(tenantId));
  return all.sort((a, b) => b.created_at.localeCompare(a.created_at));
}

async function put(item: OutboxItem): Promise<void> {
  await tx("readwrite", (s) => s.put(item));
}

export async function removeOutboxItem(clientId: string): Promise<void> {
  await tx("readwrite", (s) => s.delete(clientId));
}

export async function enqueue(tenantId: string, kind: OutboxItem["kind"], payload: OutboxItem["payload"], label: string): Promise<OutboxItem> {
  const item: OutboxItem = {
    client_id: newClientId(), tenant_id: tenantId, kind, payload, label,
    created_at: new Date().toISOString(), status: "pending", server_id: null, server_note: null, error: null,
  };
  await put(item);
  return item;
}

/** Borra lo ya sincronizado de dias anteriores (la lista muestra el dia y lo pendiente). */
export async function pruneSynced(tenantId: string, keepSince: Date): Promise<void> {
  for (const item of await listOutbox(tenantId)) {
    if (item.status === "synced" && new Date(item.created_at) < keepSince) await removeOutboxItem(item.client_id);
  }
}

export interface SyncReport {
  sent: number;
  failed: number;
  /** Sin red o sesion vencida: se reintenta despues, nada se pierde. */
  stopped: "offline" | "session" | null;
}

/** Envia lo pendiente del tenant actual: mediciones primero, despues tomas. */
export async function syncOutbox(tenantId: string): Promise<SyncReport> {
  const report: SyncReport = { sent: 0, failed: 0, stopped: null };
  const items = (await listOutbox(tenantId)).filter((i) => i.status === "pending").reverse();
  const ordered = [...items.filter((i) => i.kind === "reading"), ...items.filter((i) => i.kind === "log")];
  const readingIds = new Map<string, string>(
    (await listOutbox(tenantId)).filter((i) => i.kind === "reading" && i.server_id).map((i) => [i.client_id, i.server_id!]),
  );
  for (const item of ordered) {
    try {
      if (item.kind === "reading") {
        const p = item.payload as ReadingPayload;
        const r = await recordFieldReading({ ...p, client_id: item.client_id });
        readingIds.set(item.client_id, r.reading_id);
        item.server_id = r.reading_id;
        item.server_note = [r.result_label, r.finding_created ? "abrió un hallazgo" : r.finding_id ? "sumado al hallazgo abierto" : null]
          .filter(Boolean).join(" · ") || null;
      } else {
        const p = item.payload as LogPayload;
        let readingId: string | null = null;
        if (p.reading_client_id) {
          readingId = readingIds.get(p.reading_client_id) ?? null;
          if (!readingId) throw new ApiError(422, "La medición ligada todavía no se envió o falló");
        }
        const { reading_client_id: _ignored, ...rest } = p;
        void _ignored;
        const e = await createOperationLogEntry({ ...rest, reading_id: readingId, client_id: item.client_id });
        item.server_id = e.entry_id;
        item.server_note = e.status === "alert" ? "quedó en Alerta" : "Bueno";
      }
      item.status = "synced";
      item.error = null;
      report.sent += 1;
      await put(item);
    } catch (err) {
      // Sin red o servidor caido (5xx): se para y se reintenta despues; no es culpa del dato.
      if (!(err instanceof ApiError) || err.status >= 500) {
        report.stopped = "offline";
        break;
      }
      if (err.status === 401) {
        report.stopped = "session";
        break;
      }
      item.status = "failed";
      item.error = err.message;
      report.failed += 1;
      await put(item);
    }
  }
  return report;
}

/** Vuelve a dejar pendiente un elemento que fallo (p. ej. despues de corregir un punto). */
export async function retryOutboxItem(item: OutboxItem): Promise<void> {
  await put({ ...item, status: "pending", error: null });
}

// ── Foto de los datos para trabajar sin red ───────────────────────────

const SNAPSHOT_PREFIX = "renfygrid_operator_snapshot_";

export function saveSnapshot<T>(tenantId: string, data: T): void {
  try {
    localStorage.setItem(SNAPSHOT_PREFIX + tenantId, JSON.stringify({ saved_at: new Date().toISOString(), data }));
  } catch {
    // Sin espacio o almacenamiento bloqueado: la app sigue, solo sin foto.
  }
}

export function loadSnapshot<T>(tenantId: string): { saved_at: string; data: T } | null {
  try {
    const raw = localStorage.getItem(SNAPSHOT_PREFIX + tenantId);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}
