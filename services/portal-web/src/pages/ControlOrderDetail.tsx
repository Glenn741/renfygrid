import { useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { getControlOrderDetail } from "../api";
import { StagePage } from "../components/StagePage";

export function ControlOrderDetailPage() {
  const { orderId } = useParams<{ orderId: string }>();
  const { data, isLoading, error } = useQuery({
    queryKey: ["control-order-detail", orderId],
    queryFn: () => getControlOrderDetail(orderId!),
    enabled: !!orderId,
  });

  return (
    <StagePage title="Detalle de orden de control">
      {isLoading && <p className="text-sm text-slate-500">Cargando...</p>}
      {error && <p className="text-sm text-red-600">No se encontró la orden.</p>}
      {data && (
        <div className="space-y-4">
          <div className="rounded-xl border border-slate-200 bg-white p-5">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
              <div>
                <span className="block text-xs uppercase text-slate-400">Cuenta</span>
                <span className="font-medium text-slate-900">{data.account_number}</span>
              </div>
              <div>
                <span className="block text-xs uppercase text-slate-400">Tipo</span>
                <span className="font-medium text-slate-900">{data.type}</span>
              </div>
              <div>
                <span className="block text-xs uppercase text-slate-400">Estado</span>
                <span className="font-medium text-slate-900">{data.status}</span>
              </div>
              <div>
                <span className="block text-xs uppercase text-slate-400">Solicitada por</span>
                <span className="font-medium text-slate-900">{data.requested_by}</span>
              </div>
            </div>
            {data.justification && <p className="text-sm text-slate-600 mt-3">"{data.justification}"</p>}
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-5">
            <h2 className="text-sm font-semibold text-slate-900 mb-3">Auditoría (inmutable)</h2>
            <ol className="space-y-2">
              {data.audit.map((event, i) => (
                <li key={i} className="text-sm text-slate-600 flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-indigo-500" />
                  <span className="font-medium text-slate-900">{event.new_status}</span>
                  <span>por {event.actor}</span>
                  <span className="text-slate-400">— {new Date(event.timestamp).toLocaleString()}</span>
                </li>
              ))}
            </ol>
          </div>
        </div>
      )}
    </StagePage>
  );
}
