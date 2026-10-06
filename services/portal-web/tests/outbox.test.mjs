// npm run test:offline -- Track D, D1.3.
// Prueba de la cola sin conexion (src/offline/outbox.ts) con IndexedDB
// simulado y una API simulada que reproduce el contrato real: idempotencia
// por client_id, 422 por dato invalido, 401 por sesion vencida, red caida.
import "fake-indexeddb/auto";
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { pathToFileURL } from "node:url";

const SRC = new URL("../src/offline/outbox.ts", import.meta.url);
const GEN = new URL("./.gen/", import.meta.url);
mkdirSync(GEN, { recursive: true });
writeFileSync(new URL("outbox.ts", GEN), readFileSync(SRC, "utf8").replace('from "../api"', 'from "./api_mock.ts"'));
writeFileSync(new URL("api_mock.ts", GEN), `
export class ApiError extends Error { constructor(public status: number, message: string) { super(message); } }
export const state: any = (globalThis as any).__api;
export function getToken() { return state.token; }
export async function recordFieldReading(body: any) { return state.reading(body); }
export async function createOperationLogEntry(body: any) { return state.log(body); }
`);

let checks = 0;
function check(cond, msg) { if (!cond) throw new Error("FALLA: " + msg); checks++; console.log("  OK ", msg); }

const b64 = (o) => Buffer.from(JSON.stringify(o)).toString("base64url");
const api = {
  token: `x.${b64({ tenant_id: "T1" })}.y`,
  mode: "ok",            // ok | offline | session
  readings: new Map(),   // client_id -> server record
  logs: new Map(),
  calls: [],
};
globalThis.__api = api;
const { ApiError } = await import(new URL("api_mock.ts", GEN).href);
api.reading = async (body) => {
  api.calls.push(["reading", body.client_id]);
  if (api.mode === "offline") throw new TypeError("Failed to fetch");
  if (api.mode === "session") throw new ApiError(401, "Sesión vencida");
  if (api.mode === "server") throw new ApiError(502, "Bad gateway");
  if (body.sampling_point_id === "borrado") throw new ApiError(404, "No existe el punto");
  if (api.readings.has(body.client_id)) return { ...api.readings.get(body.client_id), duplicate: true };
  const r = { reading_id: "R" + (api.readings.size + 1), result_label: body.value < 0.3 ? "Bajo" : "Adecuado",
              finding_created: body.value < 0.3, finding_id: body.value < 0.3 ? "F1" : null };
  api.readings.set(body.client_id, r);
  return { ...r, duplicate: false };
};
api.log = async (body) => {
  api.calls.push(["log", body.client_id, body.reading_id]);
  if (api.mode === "offline") throw new TypeError("Failed to fetch");
  if (api.logs.has(body.client_id)) return { ...api.logs.get(body.client_id), duplicate: true };
  const e = { entry_id: "E" + (api.logs.size + 1), status: body.reading_id === "R1" ? "alert" : "good", reading_id: body.reading_id };
  api.logs.set(body.client_id, e);
  return e;
};

const ob = await import(new URL("outbox.ts", GEN).href);

console.log("1. Sin conexion: se encola todo, nada se pierde");
check(ob.tokenTenantId() === "T1", "el tenant sale del token");
api.mode = "offline";
const r1 = await ob.enqueue("T1", "reading", { parameter_code: "free_chlorine", value: 0.2, sampling_point_id: "P-far", action_taken: null, measured_at: "2026-10-06T16:00:00Z" }, "Cloro 0,2");
const l1 = await ob.enqueue("T1", "log", { moment_code: "afternoon", tank_level_pct: 70, chlorine_applied: null, chlorine_applied_unit: null, reading_client_id: r1.client_id, appearance: "clear", status: "alert", notes: null, logged_at: "2026-10-06T16:15:00Z" }, "Bitácora tarde");
await ob.enqueue("T2", "reading", { parameter_code: "free_chlorine", value: 1, sampling_point_id: "X", action_taken: null, measured_at: "2026-10-06T16:00:00Z" }, "otra junta");
check(/^[0-9a-f-]{36}$/.test(r1.client_id), "client_id es un UUID");
let rep = await ob.syncOutbox("T1");
check(rep.stopped === "offline" && rep.sent === 0, "sin red: se detiene sin marcar fallas");
check((await ob.listOutbox("T1")).every((i) => i.status === "pending"), "todo sigue pendiente");

console.log("2. Vuelve la senal: mediciones primero, la toma apunta a la medicion del servidor");
api.mode = "ok"; api.calls = [];
rep = await ob.syncOutbox("T1");
check(rep.sent === 2 && rep.failed === 0 && rep.stopped === null, "2 enviados");
check(api.calls[0][0] === "reading" && api.calls[1][0] === "log", "orden: medición antes que la toma");
check(api.calls[1][2] === "R1", "la toma usa el reading_id que asignó el servidor");
const items = await ob.listOutbox("T1");
check(items.find((i) => i.client_id === r1.client_id).server_note.includes("abrió un hallazgo"), "nota del servidor: abrió hallazgo");
check(items.find((i) => i.client_id === l1.client_id).server_note === "quedó en Alerta", "la toma quedó en Alerta");
check(api.calls.every((c) => c[1] !== undefined) && !api.calls.some((c) => c[0] === "reading" && c[1] === "otra"), "no envía lo de otra junta");
check((await ob.listOutbox("T2")).length === 1 && (await ob.listOutbox("T2"))[0].status === "pending", "lo de la otra junta queda intacto");

console.log("3. Corte a mitad de la sincronizacion: reenviar no duplica");
const r2 = await ob.enqueue("T1", "reading", { parameter_code: "free_chlorine", value: 0.8, sampling_point_id: "P-tank", action_taken: null, measured_at: "2026-10-06T17:00:00Z" }, "Cloro 0,8");
// Simula que el servidor guardo pero la respuesta se perdio: se registra en el servidor sin marcar en la cola.
await api.reading({ ...((await ob.listOutbox("T1")).find((i) => i.client_id === r2.client_id).payload), client_id: r2.client_id });
api.calls = [];
rep = await ob.syncOutbox("T1");
check(rep.sent === 1 && api.readings.size === 2, "el reenvío devuelve lo ya guardado: 2 mediciones en el servidor, no 3");

console.log("4. Dato rechazado (4xx): queda Rechazado con el motivo; se puede reintentar o descartar");
const bad = await ob.enqueue("T1", "reading", { parameter_code: "free_chlorine", value: 1, sampling_point_id: "borrado", action_taken: null, measured_at: "2026-10-06T17:30:00Z" }, "punto borrado");
const badLog = await ob.enqueue("T1", "log", { moment_code: "close", tank_level_pct: null, chlorine_applied: null, chlorine_applied_unit: null, reading_client_id: bad.client_id, appearance: null, status: "good", notes: null, logged_at: "2026-10-06T18:00:00Z" }, "cierre");
rep = await ob.syncOutbox("T1");
const after = await ob.listOutbox("T1");
check(rep.failed === 2, "la medición y la toma que dependía de ella quedan rechazadas");
check(after.find((i) => i.client_id === bad.client_id).error === "No existe el punto", "con el motivo del servidor");
await ob.removeOutboxItem(bad.client_id);
check(!(await ob.listOutbox("T1")).some((i) => i.client_id === bad.client_id), "descartar borra el elemento");
check(after.find((i) => i.client_id === badLog.client_id).status === "failed", "la toma dependiente no se envió sin su medición");

console.log("5. Sesion vencida o servidor caido: se detiene, nada se marca como fallido");
await ob.enqueue("T1", "reading", { parameter_code: "free_chlorine", value: 1.1, sampling_point_id: "P-mid", action_taken: null, measured_at: "2026-10-06T18:30:00Z" }, "Cloro 1,1");
api.mode = "session";
rep = await ob.syncOutbox("T1");
check(rep.stopped === "session" && rep.failed === 0, "401: se para y pide ingresar de nuevo");
api.mode = "server";
rep = await ob.syncOutbox("T1");
check(rep.stopped === "offline" && rep.failed === 0, "5xx: se reintenta después, no culpa al dato");
api.mode = "ok";
rep = await ob.syncOutbox("T1");
check(rep.sent === 1, "al volver, se envía");

console.log("6. Limpieza de lo ya enviado de dias anteriores");
await ob.pruneSynced("T1", new Date("2099-01-01"));
check((await ob.listOutbox("T1")).every((i) => i.status !== "synced"), "lo enviado se borra; lo rechazado queda");

console.log(`COLA SIN CONEXION OK (${checks} verificaciones)`);
