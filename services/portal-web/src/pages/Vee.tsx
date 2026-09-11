import { useQuery } from "@tanstack/react-query";
import { getInvalidReadings } from "../api";
import { StagePage, EmptyState } from "../components/StagePage";

export function VeePage() {
  const { data, isLoading } = useQuery({
    queryKey: ["invalid-readings"],
    queryFn: getInvalidReadings,
    refetchInterval: 30_000,
  });

  return (
    <StagePage title="Validación (VEE)">
      {isLoading && <p className="text-sm text-slate-500">Cargando...</p>}
      {data && data.length === 0 && <EmptyState message="Sin lecturas inválidas pendientes. 👍" />}
      {data && data.length > 0 && (
        <div className="overflow-x-auto rounded-xl border border-amber-200 bg-white">
          <table className="w-full text-sm">
            <thead className="bg-amber-50 text-left text-xs uppercase tracking-wide text-amber-700">
              <tr>
                <th className="px-4 py-3">Cuenta</th>
                <th className="px-4 py-3">Canal</th>
                <th className="px-4 py-3">Timestamp</th>
                <th className="px-4 py-3">Valor</th>
                <th className="px-4 py-3">Motivo</th>
              </tr>
            </thead>
            <tbody>
              {data.map((reading, i) => (
                <tr key={`${reading.meter_id}-${reading.channel}-${reading.timestamp}-${i}`}>
                  <td className="px-4 py-3 font-medium text-slate-900">{reading.account_number}</td>
                  <td className="px-4 py-3 text-slate-600">{reading.channel}</td>
                  <td className="px-4 py-3 text-slate-600">{new Date(reading.timestamp).toLocaleString()}</td>
                  <td className="px-4 py-3 tabular-nums">{reading.value}</td>
                  <td className="px-4 py-3 text-amber-700">{reading.validation_notes ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </StagePage>
  );
}
