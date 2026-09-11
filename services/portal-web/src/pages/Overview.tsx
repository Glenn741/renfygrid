import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { getDashboardOverview } from "../api";
import { KpiTile } from "../components/KpiTile";
import { useAuth } from "../auth";

// Nivel 1 (F48, Sprint C1): un tile por etapa del pipeline, patron
// exception-first -- ver docs/02-arquitectura-general.md SS9.
export function OverviewPage() {
  const { logout } = useAuth();
  const { data, isLoading, error } = useQuery({
    queryKey: ["dashboard-overview"],
    queryFn: getDashboardOverview,
    refetchInterval: 30_000,
  });

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white px-6 py-4 flex items-center justify-between">
        <h1 className="text-lg font-bold text-slate-900">RenfyGrid — Vista general</h1>
        <div className="flex items-center gap-4">
          <Link to="/observability" className="text-sm text-slate-500 hover:text-slate-700">
            Observabilidad
          </Link>
          <button onClick={logout} className="text-sm text-slate-500 hover:text-slate-700">
            Cerrar sesión
          </button>
        </div>
      </header>

      <main className="p-6">
        {isLoading && <p className="text-sm text-slate-500">Cargando...</p>}
        {error && <p className="text-sm text-red-600">No se pudo cargar el tablero.</p>}

        {data && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <KpiTile
              to="/meters"
              label="Medidores caídos"
              value={data.hes.meters_stale}
              alert={data.hes.meters_stale > 0}
              hint={`de ${data.hes.meters_total} activos`}
            />
            <KpiTile
              to="/vee"
              label="Lecturas VEE inválidas"
              value={data.vee.invalid_pending}
              alert={data.vee.invalid_pending > 0}
              hint="pendientes de revisión"
            />
            <KpiTile
              to="/consumption"
              label="Consumos en revisión"
              value={data.consumption.under_review}
              alert={data.consumption.under_review > 0}
              hint="retenidos de facturación"
            />
            <KpiTile
              to="/control"
              label="Órdenes por aprobar"
              value={data.control.pending_approval}
              alert={data.control.pending_approval > 0}
              hint="control (SCR)"
            />
          </div>
        )}
      </main>
    </div>
  );
}
