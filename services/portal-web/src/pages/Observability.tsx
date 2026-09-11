import { useQuery } from "@tanstack/react-query";
import { getIngestionMetrics } from "../api";
import { StagePage, EmptyState } from "../components/StagePage";

export function ObservabilityPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["ingestion-metrics"],
    queryFn: () => getIngestionMetrics(),
    refetchInterval: 30_000,
  });

  return (
    <StagePage title="Observabilidad">
      {isLoading && <p className="text-sm text-slate-500">Cargando...</p>}
      {data && data.alerts.length === 0 && <EmptyState message="Sin alertas activas. Todo dentro de lo esperado." />}
      {data && data.alerts.length > 0 && (
        <div className="overflow-x-auto rounded-xl border border-amber-200 bg-white">
          <table className="w-full text-sm">
            <thead className="bg-amber-50 text-left text-xs uppercase tracking-wide text-amber-700">
              <tr>
                <th className="px-4 py-3">Cuenta</th>
                <th className="px-4 py-3">Tipo de alerta</th>
                <th className="px-4 py-3">Detalle</th>
              </tr>
            </thead>
            <tbody>
              {data.alerts.map((alert, i) => (
                <tr key={`${alert.meter_id}-${i}`}>
                  <td className="px-4 py-3 font-medium text-slate-900">{alert.account_number}</td>
                  <td className="px-4 py-3 text-slate-600">{alert.type}</td>
                  <td className="px-4 py-3 text-amber-700">{alert.detail}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </StagePage>
  );
}
