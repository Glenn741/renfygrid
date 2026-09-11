import { useQuery } from "@tanstack/react-query";
import { getDashboardOverview } from "../api";
import { KpiTile } from "../components/KpiTile";
import { AppShell } from "../components/AppShell";

// Nivel 1 (F48, Sprint C1): un tile por etapa del pipeline, patron
// exception-first -- ver docs/02-arquitectura-general.md SS9. Sprint C9:
// el header/nav propio de esta pantalla se reemplaza por AppShell (mismo
// shell que las otras 8 pantallas) -- el contenido (queries, KPIs) no cambia.
export function OverviewPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["dashboard-overview"],
    queryFn: getDashboardOverview,
    refetchInterval: 30_000,
  });

  return (
    <AppShell title="Vista general">
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
    </AppShell>
  );
}
