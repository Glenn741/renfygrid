import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { getServiceOrders, type ServiceOrder } from "../api";
import { StagePage, EmptyState } from "../components/StagePage";

// Nivel 2 (Sprint C6, sobre el endpoint unificado de C5): junta ordenes de
// control + lecturas bajo demanda/pings en una sola cola, con el origen
// (CIS externo / Portal / Sistema) y el modo (automatico/manual) ya
// resueltos por el backend -- ver docs/06-benchmark-e2e-y-brechas.md SS2-3.

const KIND_LABEL: Record<ServiceOrder["kind"], string> = {
  control_order: "Orden de control",
  on_demand_read: "Lectura bajo demanda",
  ping: "Ping / estado",
};

type ModeFilter = "todas" | "automatico" | "manual";

export function IntegrationsPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["service-orders"],
    queryFn: getServiceOrders,
    refetchInterval: 30_000,
  });

  const [modeFilter, setModeFilter] = useState<ModeFilter>("todas");

  const rows = useMemo(() => {
    if (!data) return [];
    if (modeFilter === "todas") return data;
    return data.filter((row) => row.mode === modeFilter);
  }, [data, modeFilter]);

  const summary = useMemo(() => {
    if (!data) return { total: 0, automatico: 0, manual: 0 };
    return {
      total: data.length,
      automatico: data.filter((r) => r.mode === "automatico").length,
      manual: data.filter((r) => r.mode === "manual").length,
    };
  }, [data]);

  return (
    <StagePage title="Integraciones (CIS)">
      {isLoading && <p className="text-sm text-slate-500">Cargando...</p>}

      {data && (
        <>
          <div className="mb-4 grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <div className="text-2xl font-bold text-slate-900">{summary.total}</div>
              <div className="text-xs text-slate-500 mt-1">Peticiones en el registro</div>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <div className="text-2xl font-bold text-emerald-700">{summary.automatico}</div>
              <div className="text-xs text-slate-500 mt-1">Resueltas automáticamente</div>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <div className="text-2xl font-bold text-amber-700">{summary.manual}</div>
              <div className="text-xs text-slate-500 mt-1">Con aprobación manual</div>
            </div>
          </div>

          <div className="mb-4 flex gap-2">
            {(["todas", "automatico", "manual"] as ModeFilter[]).map((f) => (
              <button
                key={f}
                onClick={() => setModeFilter(f)}
                className={`rounded-full px-3 py-1 text-xs font-semibold border ${
                  modeFilter === f
                    ? "bg-indigo-600 text-white border-indigo-600"
                    : "bg-white text-slate-600 border-slate-200 hover:border-slate-300"
                }`}
              >
                {f === "todas" ? "Todas" : f === "automatico" ? "Automáticas" : "Manuales"}
              </button>
            ))}
          </div>

          {rows.length === 0 && <EmptyState message="Sin peticiones que mostrar con este filtro." />}
          {rows.length > 0 && (
            <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
              <table className="w-full text-sm">
                <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
                  <tr>
                    <th className="px-4 py-3">Hora</th>
                    <th className="px-4 py-3">Tipo</th>
                    <th className="px-4 py-3">Cuenta</th>
                    <th className="px-4 py-3">Origen</th>
                    <th className="px-4 py-3">Modo</th>
                    <th className="px-4 py-3">Estado</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={`${row.kind}-${row.id}`}>
                      <td className="px-4 py-3 text-slate-500">
                        {row.timestamp ? new Date(row.timestamp).toLocaleString() : "—"}
                      </td>
                      <td className="px-4 py-3 font-medium text-slate-900">
                        {KIND_LABEL[row.kind]}
                        {row.kind === "control_order" ? ` (${row.type})` : ""}
                      </td>
                      <td className="px-4 py-3 text-slate-600">{row.account_number}</td>
                      <td className="px-4 py-3">
                        <span
                          className={`rounded-full px-2 py-0.5 text-xs font-semibold ${
                            row.origin === "CIS externo"
                              ? "bg-slate-100 text-slate-700"
                              : row.origin === "Portal (operador)"
                              ? "bg-indigo-50 text-indigo-700"
                              : row.origin === "Sistema"
                              ? "bg-slate-50 text-slate-500"
                              : "bg-red-50 text-red-600"
                          }`}
                        >
                          {row.origin}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={`rounded-full px-2 py-0.5 text-xs font-semibold ${
                            row.mode === "automatico" ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"
                          }`}
                        >
                          {row.mode === "automatico" ? "Automático" : "Manual"}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-slate-600">{row.status}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <div className="mt-4 rounded-xl border border-indigo-100 bg-indigo-50/40 p-4 text-sm text-slate-600">
            <b className="text-slate-900">¿Qué decide si una petición se resuelve sola o espera aprobación?</b>{" "}
            Lecturas y pings siempre son automáticos. Las órdenes de control (suspensión,
            reconexión, desconexión) siguen la regla vigente en{" "}
            <Link to="/configuration" className="text-indigo-600 hover:text-indigo-700 font-medium">
              Configuración → Niveles de aprobación de control
            </Link>
            .
          </div>
        </>
      )}
    </StagePage>
  );
}
