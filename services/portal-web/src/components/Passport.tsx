import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, getPassport, setProductRecord, type PassportProduct, type PassportSummary, type ProductStatus } from "../api";
import { ROUTE_QUERY_KEY } from "./routeStatus";

// Pasaporte de productos (Guia 7, T-07, migracion 0028): que producto se
// construyo, que evidencia existe y que debe validarse o pasar al Plan de
// Mejora. Los productos son catalogo del paquete del programa; el estado es
// de cada junta. Un producto sin registrar se muestra como pendiente.

export const PRODUCT_STATUS: Record<ProductStatus, { label: string; pill: string; button: string }> = {
  complete: { label: "Completo", pill: "bg-emerald-50 text-emerald-700", button: "bg-emerald-600 border-emerald-600 text-white" },
  to_validate: { label: "Por validar", pill: "bg-amber-50 text-amber-800", button: "bg-amber-500 border-amber-500 text-white" },
  pending: { label: "Pendiente", pill: "bg-slate-100 text-slate-700", button: "bg-slate-600 border-slate-600 text-white" },
};
const STATUS_ORDER: ProductStatus[] = ["complete", "to_validate", "pending"];

export const PASSPORT_QUERY_KEY = ["passport"] as const;

export function passportText(s: PassportSummary): string {
  return `${s.complete} de ${s.total} completos${s.to_validate ? ` · ${s.to_validate} por validar` : ""}`;
}

function ProductRow({ product }: { product: PassportProduct }) {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [status, setStatus] = useState<ProductStatus>(product.status);
  const [evidence, setEvidence] = useState(product.evidence ?? "");
  const [toPlan, setToPlan] = useState(product.to_improvement_plan);
  const [error, setError] = useState<string | null>(null);
  const st = PRODUCT_STATUS[product.status];

  const open = () => {
    setStatus(product.status);
    setEvidence(product.evidence ?? "");
    setToPlan(product.to_improvement_plan);
    setError(null);
    setEditing(true);
  };

  const mutation = useMutation({
    mutationFn: () => setProductRecord(product.pack_id, product.code, { status, evidence: evidence || null, to_improvement_plan: toPlan }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ROUTE_QUERY_KEY });
      queryClient.invalidateQueries({ queryKey: PASSPORT_QUERY_KEY });
      setEditing(false);
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "No se pudo guardar."),
  });

  return (
    <li className="py-2.5">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${st.pill}`}>{st.label}</span>
        <span className="min-w-0 flex-1 text-sm text-slate-800">
          {product.title}
          {product.to_improvement_plan && <span className="ml-2 rounded-full bg-indigo-50 px-2 py-0.5 text-[11px] font-semibold text-indigo-700">Pasa a G6</span>}
          {product.evidence && <span className="block text-xs text-slate-500">Evidencia: {product.evidence}</span>}
          {!product.registered && <span className="block text-xs text-slate-400">Sin registrar todavía</span>}
        </span>
        {!editing && (
          <button onClick={open} className="rounded-lg border border-slate-300 px-3 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50">
            Actualizar
          </button>
        )}
      </div>
      {editing && (
        <div className="mt-2 space-y-2 rounded-lg border border-slate-200 bg-slate-50 p-3">
          <div role="radiogroup" aria-label={`Estado de ${product.title}`} className="flex flex-wrap gap-2">
            {STATUS_ORDER.map((code) => (
              <label key={code} className={`inline-flex cursor-pointer items-center rounded-lg border-2 px-3 py-1 text-sm font-semibold has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-indigo-500 ${status === code ? PRODUCT_STATUS[code].button : "border-slate-300 bg-white text-slate-700 hover:bg-slate-50"}`}>
                <input type="radio" className="sr-only" name={`st-${product.pack_id}-${product.code}`} checked={status === code} onChange={() => setStatus(code)} />
                {PRODUCT_STATUS[code].label}
              </label>
            ))}
          </div>
          <input
            aria-label="Evidencia"
            className="w-full rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm"
            placeholder="Evidencia: dónde está (carpeta, acta, foto, archivo)"
            value={evidence}
            onChange={(e) => setEvidence(e.target.value)}
          />
          <label className="flex items-center gap-2 text-sm text-slate-700">
            <input type="checkbox" checked={toPlan} onChange={(e) => setToPlan(e.target.checked)} />
            Pasa al Plan de Mejora (Guía 6)
          </label>
          {error && <p className="text-sm text-red-600">{error}</p>}
          <div className="flex gap-2">
            <button onClick={() => mutation.mutate()} disabled={mutation.isPending} className="rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-50">
              {mutation.isPending ? "Guardando…" : "Guardar"}
            </button>
            <button onClick={() => setEditing(false)} className="px-2 text-sm text-slate-500 hover:text-slate-700">Cancelar</button>
          </div>
        </div>
      )}
    </li>
  );
}

/** Productos de una etapa de la ruta, editables en el mismo lugar. */
export function StageProducts({ products, summary }: { products: PassportProduct[]; summary: PassportSummary }) {
  if (products.length === 0) return null;
  return (
    <div className="mt-4 rounded-lg border border-slate-200 p-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-sm font-semibold text-slate-900">Productos de la etapa · pasaporte</h3>
        <span className="text-xs text-slate-500 tabular-nums">{passportText(summary)}</span>
      </div>
      <ul className="divide-y divide-slate-100">
        {products.map((p) => <ProductRow key={`${p.pack_id}-${p.code}`} product={p} />)}
      </ul>
    </div>
  );
}

/** Pasaporte completo (T-07): todas las etapas, para la revision del dia 8. */
export function PassportView({ onClose }: { onClose: () => void }) {
  const { data, isLoading } = useQuery({ queryKey: PASSPORT_QUERY_KEY, queryFn: getPassport });
  return (
    <section className="space-y-4 rounded-xl border border-indigo-200 bg-white p-5">
      <div>
        <button onClick={onClose} className="mb-2 text-sm font-medium text-indigo-700 hover:underline">← Volver a la ruta</button>
        <h2 className="text-base font-semibold text-slate-900">Pasaporte de productos</h2>
        <p className="text-sm text-slate-600">
          Qué producto se construyó, qué evidencia existe y qué debe validarse o pasar al Plan de Mejora. Se actualiza al cierre de cada jornada y se revisa completo al final.
        </p>
      </div>
      {isLoading && <p className="text-sm text-slate-500">Cargando…</p>}
      {data && (
        <>
          <div className="flex flex-wrap gap-2 text-xs">
            {STATUS_ORDER.map((code) => (
              <span key={code} className={`rounded-full px-2.5 py-1 font-semibold tabular-nums ${PRODUCT_STATUS[code].pill}`}>
                {data.summary[code]} {PRODUCT_STATUS[code].label.toLowerCase()}
              </span>
            ))}
            <span className="rounded-full bg-indigo-50 px-2.5 py-1 font-semibold text-indigo-700 tabular-nums">{data.summary.to_improvement_plan} pasan a G6</span>
          </div>
          {data.stages.filter((s) => s.products.length > 0).map((s) => (
            <div key={`${s.pack_id}-${s.code}`}>
              <div className="flex flex-wrap items-baseline justify-between gap-2 border-b border-slate-200 pb-1">
                <h3 className="text-sm font-semibold text-slate-900">Etapa {s.order} · {s.title}</h3>
                <span className="text-xs text-slate-500">{s.source_ref} · {passportText(s.summary)}</span>
              </div>
              <ul className="divide-y divide-slate-100">
                {s.products.map((p) => <ProductRow key={`${p.pack_id}-${p.code}`} product={p} />)}
              </ul>
            </div>
          ))}
        </>
      )}
    </section>
  );
}
