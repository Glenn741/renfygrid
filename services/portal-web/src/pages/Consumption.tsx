import { useQuery } from "@tanstack/react-query";
import { getConsumptionUnderReview } from "../api";
import { StagePage, EmptyState } from "../components/StagePage";

export function ConsumptionPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["consumption-under-review"],
    queryFn: getConsumptionUnderReview,
    refetchInterval: 30_000,
  });

  return (
    <StagePage title="Consumos">
      {isLoading && <p className="text-sm text-slate-500">Cargando...</p>}
      {data && data.length === 0 && <EmptyState message="Sin consumos en revisión. Nada retenido de facturación." />}
      {data && data.length > 0 && (
        <div className="overflow-x-auto rounded-xl border border-amber-200 bg-white">
          <table className="w-full text-sm">
            <thead className="bg-amber-50 text-left text-xs uppercase tracking-wide text-amber-700">
              <tr>
                <th className="px-4 py-3">Cuenta</th>
                <th className="px-4 py-3">Periodo</th>
                <th className="px-4 py-3">Consumo</th>
                <th className="px-4 py-3">Estado</th>
              </tr>
            </thead>
            <tbody>
              {data.map((row) => (
                <tr key={`${row.meter_id}-${row.period}`}>
                  <td className="px-4 py-3 font-medium text-slate-900">{row.account_number}</td>
                  <td className="px-4 py-3 text-slate-600">{row.period}</td>
                  <td className="px-4 py-3 tabular-nums">{row.value}</td>
                  <td className="px-4 py-3 text-amber-700">En revisión</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </StagePage>
  );
}
