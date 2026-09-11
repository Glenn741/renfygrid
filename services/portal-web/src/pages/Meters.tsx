import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, getIngestionMetrics, readMeterNow } from "../api";
import { StagePage, EmptyState } from "../components/StagePage";

export function MetersPage() {
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["ingestion-metrics"],
    queryFn: () => getIngestionMetrics(),
    refetchInterval: 30_000,
  });

  const [channel, setChannel] = useState("active_energy");
  const [error, setError] = useState<string | null>(null);
  const [lastRead, setLastRead] = useState<{ meterId: string; value: number } | null>(null);

  const readNowMutation = useMutation({
    mutationFn: (meterId: string) => readMeterNow(meterId, channel),
    onSuccess: (reading, meterId) => {
      setError(null);
      setLastRead({ meterId, value: reading.value });
      queryClient.invalidateQueries({ queryKey: ["ingestion-metrics"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard-overview"] });
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "No se pudo leer el medidor ahora."),
  });

  return (
    <StagePage title="Medidores / HES">
      <div className="mb-4 flex flex-wrap items-end gap-3 rounded-xl border border-slate-200 bg-white p-4">
        <div>
          <label className="block text-xs font-medium text-slate-500 mb-1">Canal para "Leer ahora"</label>
          <input
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm"
            value={channel}
            onChange={(e) => setChannel(e.target.value)}
          />
        </div>
        {error && <p className="text-sm text-red-600">{error}</p>}
        {lastRead && !error && (
          <p className="text-sm text-emerald-700">Última lectura bajo demanda: {lastRead.value}</p>
        )}
      </div>

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
                <th className="px-4 py-3"></th>
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
                  <td className="px-4 py-3">
                    <button
                      onClick={() => readNowMutation.mutate(meter.meter_id)}
                      disabled={readNowMutation.isPending}
                      className="rounded-lg bg-indigo-600 text-white text-xs font-semibold px-3 py-1.5 hover:bg-indigo-700 disabled:opacity-40"
                    >
                      Leer ahora
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </StagePage>
  );
}
