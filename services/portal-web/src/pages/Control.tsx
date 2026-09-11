import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, approveControlOrder, getControlOrders } from "../api";
import { StagePage, EmptyState } from "../components/StagePage";

export function ControlPage() {
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["control-orders", "pending_approval"],
    queryFn: () => getControlOrders("pending_approval"),
    refetchInterval: 30_000,
  });

  const [error, setError] = useState<string | null>(null);

  const approveMutation = useMutation({
    mutationFn: (orderId: string) => approveControlOrder(orderId),
    onSuccess: () => {
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["control-orders"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard-overview"] });
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "No se pudo aprobar la orden."),
  });

  return (
    <StagePage title="Control (SCR)">
      {error && (
        <div className="mb-4 rounded-xl border border-red-200 bg-red-50 p-3">
          <p className="text-sm text-red-600">{error}</p>
        </div>
      )}

      {isLoading && <p className="text-sm text-slate-500">Cargando...</p>}
      {data && data.length === 0 && <EmptyState message="Sin órdenes pendientes de aprobación." />}
      {data && data.length > 0 && (
        <div className="overflow-x-auto rounded-xl border border-amber-200 bg-white">
          <table className="w-full text-sm">
            <thead className="bg-amber-50 text-left text-xs uppercase tracking-wide text-amber-700">
              <tr>
                <th className="px-4 py-3">Cuenta</th>
                <th className="px-4 py-3">Tipo</th>
                <th className="px-4 py-3">Solicitada por</th>
                <th className="px-4 py-3">Justificación</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody>
              {data.map((order) => (
                <tr key={order.order_id}>
                  <td className="px-4 py-3 font-medium text-slate-900">
                    <Link to={`/control/${order.order_id}`} className="text-indigo-600 hover:text-indigo-700">
                      {order.account_number}
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-slate-600">{order.type}</td>
                  <td className="px-4 py-3 text-slate-600">{order.requested_by}</td>
                  <td className="px-4 py-3 text-slate-600">{order.justification ?? "—"}</td>
                  <td className="px-4 py-3">
                    <button
                      disabled={approveMutation.isPending}
                      onClick={() => approveMutation.mutate(order.order_id)}
                      className="rounded-lg bg-indigo-600 text-white text-xs font-semibold px-3 py-1.5 hover:bg-indigo-700 disabled:opacity-40"
                    >
                      Aprobar
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
