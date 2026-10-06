import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ApiError,
  createWarehouseItem,
  getChemicalProducts,
  getWarehouse,
  getWarehouseMovements,
  recordWarehouseMovement,
  updateWarehouseItem,
} from "../api";
import { StagePage, EmptyState } from "../components/StagePage";
import { NavSection, SectionNav } from "../components/SectionNav";
import { sectionsFor } from "../navigation";

// Bodega y EPP (Track D, D4; Guia 3 §3.9-3.10, lista 7G.1). Categorias y EPP
// por tarea salen del paquete; articulos, stock minimo y movimientos son de
// la junta. El cruce del cloro compara la bitacora 7C con las salidas.

const SECTIONS = sectionsFor("/warehouse");
const KEY = ["warehouse"];
const UNIT_LABEL: Record<string, string> = { g: "g", kg: "kg", ml: "ml", l: "L", unit: "unidad", pair: "par", m: "m" };
const KIND_LABEL: Record<string, string> = { in: "Entrada", out: "Salida", adjust: "Ajuste por conteo" };

function errText(err: unknown, fallback: string) {
  return err instanceof ApiError ? err.message : fallback;
}

function Card({ title, description, children }: { title: string; description?: string; children: React.ReactNode }) {
  return (
    <section className="mb-6 rounded-xl border border-slate-200 bg-white p-5">
      <h2 className="text-base font-semibold text-slate-900">{title}</h2>
      {description && <p className="mb-3 mt-1 max-w-3xl text-sm text-slate-600">{description}</p>}
      {children}
    </section>
  );
}

function newClientId(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : `${Date.now()}`;
}

function StatusSection() {
  const { data, error } = useQuery({ queryKey: KEY, queryFn: getWarehouse, retry: false });
  if (error) return <Card title="Estado de la bodega"><p className="text-sm text-amber-800">{errText(error, "")}</p></Card>;
  if (!data) return null;
  const alerts = data.items.filter((i) => i.below_min || i.expiring.length > 0);
  return (
    <Card title="Estado de la bodega" description="Lo que falta reponer, lo que vence antes de la próxima revisión 7G.1 y el cruce del cloro del mes.">
      {alerts.length === 0 && <EmptyState message="Sin artículos bajo el mínimo ni por vencer." />}
      <ul className="space-y-2">
        {alerts.map((i) => (
          <li key={i.item_id} className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
            <strong>{i.name}</strong>
            {i.below_min && <span> · existencia {i.stock} {UNIT_LABEL[i.unit]}, mínimo {i.min_stock}</span>}
            {i.expiring.map((l) => (
              <span key={l.expires_on} className="block text-xs">
                {l.expired ? "Vencido" : `Vence en ${l.days_left} día${l.days_left === 1 ? "" : "s"}`} ({new Date(`${l.expires_on}T12:00:00`).toLocaleDateString("es")}): quedan {l.remaining} {UNIT_LABEL[i.unit]}
              </span>
            ))}
          </li>
        ))}
      </ul>
      <h3 className="mt-4 text-sm font-semibold text-slate-900">Cloro aplicado (bitácora 7C) vs. salidas de bodega · este mes</h3>
      {data.chlorine_check.length === 0 && <p className="text-sm text-slate-500">Sin cloro registrado este mes, o el hipoclorito no está ligado a un producto desinfectante.</p>}
      {data.chlorine_check.map((c) => (
        <p key={c.unit ?? "x"} className={`mt-1 rounded-lg p-3 text-sm ${!c.comparable ? "bg-slate-50 text-slate-600" : Math.abs(c.difference_pct ?? 0) > 10 ? "bg-amber-50 text-amber-900" : "bg-emerald-50 text-emerald-800"}`}>
          {c.comparable
            ? <>Aplicado {c.applied} {c.unit} · salió de bodega {c.issued} {c.unit} · diferencia {c.difference} {c.unit}{c.difference_pct !== null ? ` (${c.difference_pct} %)` : ""}.
                {c.difference !== null && c.difference > 0 && " Salió más de lo que se registró como aplicado: revise la bitácora o pérdidas."}
                {c.difference !== null && c.difference < 0 && " Se registró más de lo que salió: falta registrar salidas de bodega."}</>
            : "Unidades no comparables (masa contra volumen)."}
        </p>
      ))}
      <Link to="/inspections/G3" className="mt-3 inline-block text-sm font-semibold text-indigo-700 hover:underline">Aplicar la revisión 7G.1 de bodega y EPP ›</Link>
    </Card>
  );
}

function ItemsSection() {
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: KEY, queryFn: getWarehouse, retry: false });
  const { data: products } = useQuery({ queryKey: ["chemical-products"], queryFn: () => getChemicalProducts() });
  const [f, setF] = useState({ name: "", category_code: "chemicals", unit: "kg", min_stock: "", chemical_product_id: "" });
  const [msg, setMsg] = useState<string | null>(null);
  const create = useMutation({
    mutationFn: () => createWarehouseItem({ name: f.name, category_code: f.category_code, unit: f.unit,
      min_stock: f.min_stock ? Number(f.min_stock) : null, chemical_product_id: f.chemical_product_id || null }),
    onSuccess: () => { setF({ ...f, name: "", min_stock: "" }); setMsg(null); qc.invalidateQueries({ queryKey: KEY }); },
    onError: (e) => setMsg(errText(e, "No se pudo crear.")),
  });
  const deactivate = useMutation({ mutationFn: (id: string) => updateWarehouseItem(id, { active: false }), onSuccess: () => qc.invalidateQueries({ queryKey: KEY }) });
  if (!data) return null;
  return (
    <Card title="Artículos" description="Químicos, repuestos, herramientas, control y EPP. El stock mínimo lo fija la junta.">
      {data.categories.map((c) => {
        const items = data.items.filter((i) => i.category_code === c.code);
        return (
          <div key={c.code} className="mb-3">
            <h3 className="text-sm font-semibold text-slate-900">{c.label}</h3>
            <p className="text-xs text-slate-500">Debe incluir: {c.should_include}</p>
            {items.length === 0 ? <p className="text-xs text-slate-400">Sin artículos todavía.</p> : (
              <ul className="divide-y divide-slate-100">
                {items.map((i) => (
                  <li key={i.item_id} className="flex flex-wrap items-center gap-3 py-1.5 text-sm">
                    <span className="flex-1 text-slate-800">{i.name}</span>
                    <span className={`tabular-nums ${i.below_min ? "font-semibold text-amber-800" : "text-slate-700"}`}>{i.stock} {UNIT_LABEL[i.unit]}</span>
                    <span className="text-xs text-slate-500">{i.min_stock !== null ? `mín. ${i.min_stock}` : "sin mínimo"}</span>
                    <button onClick={() => deactivate.mutate(i.item_id)} className="text-xs text-slate-400 hover:text-slate-700">Quitar</button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        );
      })}
      <div className="mt-3 grid gap-2 rounded-lg border border-dashed border-slate-300 bg-slate-50 p-3 sm:grid-cols-[1fr_9rem_7rem_7rem]">
        <input aria-label="Nombre" className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm" placeholder="Nombre del artículo" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} />
        <select aria-label="Categoría" className="rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-sm" value={f.category_code} onChange={(e) => setF({ ...f, category_code: e.target.value })}>
          {data.categories.map((c) => <option key={c.code} value={c.code}>{c.label}</option>)}
        </select>
        <select aria-label="Unidad" className="rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-sm" value={f.unit} onChange={(e) => setF({ ...f, unit: e.target.value })}>
          {data.units.map((u) => <option key={u} value={u}>{UNIT_LABEL[u] ?? u}</option>)}
        </select>
        <input aria-label="Stock mínimo" type="number" min={0} step="any" className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm" placeholder="Mínimo" value={f.min_stock} onChange={(e) => setF({ ...f, min_stock: e.target.value })} />
        {f.category_code === "chemicals" && (
          <select aria-label="Producto de dosificación" className="rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-sm sm:col-span-3" value={f.chemical_product_id} onChange={(e) => setF({ ...f, chemical_product_id: e.target.value })}>
            <option value="">— ligar a un producto de la dosificación (para el cruce del cloro) —</option>
            {(products ?? []).map((p) => <option key={p.product_id} value={p.product_id}>{p.name}</option>)}
          </select>
        )}
        <button onClick={() => create.mutate()} disabled={!f.name.trim()} className="rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-semibold text-white disabled:opacity-50">Agregar</button>
        {msg && <p className="text-sm text-red-600 sm:col-span-4">{msg}</p>}
      </div>
    </Card>
  );
}

function MovementSection() {
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: KEY, queryFn: getWarehouse, retry: false });
  const [f, setF] = useState({ item_id: "", kind: "out", quantity: "", expires_on: "", reason: "" });
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const save = useMutation({
    mutationFn: () => recordWarehouseMovement({ item_id: f.item_id, kind: f.kind, quantity: Number(f.quantity),
      expires_on: f.kind === "in" && f.expires_on ? f.expires_on : null, reason: f.reason || null, client_id: newClientId() }),
    onSuccess: (r) => { setF({ ...f, quantity: "", expires_on: "", reason: "" }); setMsg({ ok: true, text: `Registrado. Existencia: ${r.stock}.` });
      for (const k of [KEY, ["warehouse-movements"]]) qc.invalidateQueries({ queryKey: k }); },
    onError: (e) => setMsg({ ok: false, text: errText(e, "No se pudo registrar.") }),
  });
  if (!data) return null;
  return (
    <Card title="Registrar entrada, salida o conteo" description="Cada compra (con su fecha de vencimiento), cada salida y cada conteo físico.">
      <div className="grid gap-2 sm:grid-cols-[1fr_11rem_8rem]">
        <select aria-label="Artículo" className="rounded-lg border border-slate-300 px-2 py-1.5 text-sm" value={f.item_id} onChange={(e) => setF({ ...f, item_id: e.target.value })}>
          <option value="">— artículo —</option>
          {data.items.map((i) => <option key={i.item_id} value={i.item_id}>{i.name} ({i.stock} {UNIT_LABEL[i.unit]})</option>)}
        </select>
        <select aria-label="Movimiento" className="rounded-lg border border-slate-300 px-2 py-1.5 text-sm" value={f.kind} onChange={(e) => setF({ ...f, kind: e.target.value })}>
          {Object.entries(KIND_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
        <input aria-label="Cantidad" type="number" step="any" className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm" placeholder={f.kind === "adjust" ? "± diferencia" : "Cantidad"} value={f.quantity} onChange={(e) => setF({ ...f, quantity: e.target.value })} />
        {f.kind === "in" && (
          <label className="text-xs text-slate-600">Vence el (si aplica)
            <input type="date" className="mt-1 w-full rounded-lg border border-slate-300 px-2 py-1.5 text-sm" value={f.expires_on} onChange={(e) => setF({ ...f, expires_on: e.target.value })} />
          </label>
        )}
        <input aria-label="Motivo" className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm sm:col-span-2" placeholder="Motivo (compra, dosificación, reparación, conteo…)" value={f.reason} onChange={(e) => setF({ ...f, reason: e.target.value })} />
      </div>
      {msg && <p className={`mt-2 text-sm ${msg.ok ? "text-emerald-700" : "text-red-600"}`}>{msg.text}</p>}
      <button onClick={() => save.mutate()} disabled={!f.item_id || !f.quantity} className="mt-3 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">Registrar</button>
    </Card>
  );
}

function PpeSection() {
  const { data } = useQuery({ queryKey: KEY, queryFn: getWarehouse, retry: false });
  if (!data) return null;
  return (
    <Card title="EPP mínimo por tarea" description="La JAAPS debe cuidar a quien cuida el sistema.">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead><tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wide text-slate-500">
            <th className="py-2 pr-3">Tarea</th><th className="py-2 pr-3">EPP mínimo</th><th className="py-2">Cuidado principal</th></tr></thead>
          <tbody>
            {data.ppe_tasks.map((t) => (
              <tr key={t.task} className="border-b border-slate-100 align-top last:border-0">
                <td className="py-2 pr-3 font-medium text-slate-800">{t.task}</td><td className="py-2 pr-3 text-slate-700">{t.ppe}</td><td className="py-2 text-slate-600">{t.care}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function HistorySection() {
  const { data } = useQuery({ queryKey: ["warehouse-movements"], queryFn: () => getWarehouseMovements() });
  return (
    <Card title="Registro de bodega">
      {data && data.length === 0 && <EmptyState message="Sin movimientos todavía." />}
      <ul className="divide-y divide-slate-100">
        {(data ?? []).map((m) => (
          <li key={m.movement_id} className="py-1.5 text-sm text-slate-700">
            <span className="tabular-nums text-slate-500">{new Date(m.moved_at).toLocaleString("es", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}</span>
            {" · "}<strong>{KIND_LABEL[m.kind]}</strong> {m.quantity} {UNIT_LABEL[m.unit]} de {m.item_name}
            {m.expires_on && <span className="text-xs text-slate-500"> · vence {new Date(`${m.expires_on}T12:00:00`).toLocaleDateString("es")}</span>}
            {m.reason && <span className="text-xs text-slate-500"> · {m.reason}</span>}
          </li>
        ))}
      </ul>
    </Card>
  );
}

export function WarehousePage() {
  return (
    <StagePage title="Bodega y EPP">
      <SectionNav items={SECTIONS} />
      <NavSection id="status"><StatusSection /></NavSection>
      <NavSection id="move"><MovementSection /></NavSection>
      <NavSection id="items"><ItemsSection /></NavSection>
      <NavSection id="ppe"><PpeSection /></NavSection>
      <NavSection id="history"><HistorySection /></NavSection>
    </StagePage>
  );
}
