import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, editReading, getInvalidReadings, type InvalidReading } from "../api";
import { StagePage, EmptyState } from "../components/StagePage";

function EditReadingRow({ reading }: { reading: InvalidReading }) {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [newValue, setNewValue] = useState(String(reading.value));
  const [userName, setUserName] = useState("");
  const [justification, setJustification] = useState("");
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () =>
      editReading({
        meter_id: reading.meter_id,
        channel: reading.channel,
        timestamp: reading.timestamp,
        new_value: Number(newValue),
        user_name: userName,
        justification,
      }),
    onSuccess: () => {
      setError(null);
      setEditing(false);
      queryClient.invalidateQueries({ queryKey: ["invalid-readings"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard-overview"] });
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "No se pudo editar la lectura."),
  });

  return (
    <>
      <tr>
        <td className="px-4 py-3 font-medium text-slate-900">{reading.account_number}</td>
        <td className="px-4 py-3 text-slate-600">{reading.channel}</td>
        <td className="px-4 py-3 text-slate-600">{new Date(reading.timestamp).toLocaleString()}</td>
        <td className="px-4 py-3 tabular-nums">{reading.value}</td>
        <td className="px-4 py-3 text-amber-700">{reading.validation_notes ?? "—"}</td>
        <td className="px-4 py-3">
          <button onClick={() => setEditing((v) => !v)} className="text-xs text-indigo-600 hover:text-indigo-700">
            {editing ? "Cancelar" : "Editar"}
          </button>
        </td>
      </tr>
      {editing && (
        <tr className="bg-slate-50">
          <td colSpan={6} className="px-4 py-3">
            <div className="flex flex-wrap items-end gap-3">
              <div>
                <label className="block text-xs font-medium text-slate-500 mb-1">Valor corregido</label>
                <input className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm w-28" value={newValue} onChange={(e) => setNewValue(e.target.value)} />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-500 mb-1">Quién edita</label>
                <input className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm" value={userName} onChange={(e) => setUserName(e.target.value)} placeholder="nombre@empresa.com" />
              </div>
              <div className="flex-1 min-w-[200px]">
                <label className="block text-xs font-medium text-slate-500 mb-1">Justificación</label>
                <input className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm w-full" value={justification} onChange={(e) => setJustification(e.target.value)} placeholder="por qué se corrige" />
              </div>
              <button
                onClick={() => mutation.mutate()}
                disabled={!userName || !justification || mutation.isPending}
                className="rounded-lg bg-indigo-600 text-white text-xs font-semibold px-3 py-1.5 hover:bg-indigo-700 disabled:opacity-40"
              >
                Guardar
              </button>
            </div>
            {error && <p className="text-sm text-red-600 mt-2">{error}</p>}
          </td>
        </tr>
      )}
    </>
  );
}

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
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody>
              {data.map((reading, i) => (
                <EditReadingRow key={`${reading.meter_id}-${reading.channel}-${reading.timestamp}-${i}`} reading={reading} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </StagePage>
  );
}
