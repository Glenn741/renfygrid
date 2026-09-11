import { useQuery } from "@tanstack/react-query";
import { getIngestionMetrics } from "../api";
import { StagePage, EmptyState } from "../components/StagePage";

export function MetersPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["ingestion-metrics"],
    queryFn: () => getIngestionMetrics(),
    refetchInterval: 30_000,
  });

  return (
    <StagePage title="Medidores / HES">
      {isLoading && <p className="text-sm text-slate-500">Cargando...</p>}
      {data && data.meters.length === 0 && <EmptyState message="No hay medidores activos todavía." />}
      {data && data.meters.length > 0 && (
        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3">Cuenta</th>
                <th className="px-4 py-3">Estado</th>
                <th className="px-4 py-3">Última lectura</th>
                <th className="px-4 py-3">Lecturas 24h</th>
                <th className="px-4 py-3">Fallas de comunicación 24h</th>
              </tr>
            </thead>
            <tbody>
              {data.meters.map((meter) => (
                <tr key={meter.meter_id} className={meter.is_stale ? "bg-amber-50" : ""}>
                  <td className="px-4 py-3 font-medium text-slate-900">{meter.account_number}</td>
                  <td className="px-4 py-3">
                    {meter.is_stale ? (
                      <span className="text-amber-700">⚠ Caído</span>
                    ) : (
                      <span className="text-slate-500">Activo</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-slate-600">
                    {meter.last_reading_at ? new Date(meter.last_reading_at).toLocaleString() : "nunca"}
                  </td>
                  <td className="px-4 py-3 tabular-nums">{meter.readings_24h}</td>
                  <td className="px-4 py-3 tabular-nums">{meter.communication_failures_24h}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </StagePage>
  );
}
