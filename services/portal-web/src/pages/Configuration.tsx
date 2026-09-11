import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ApiError,
  createApprovalLevel,
  createConsumptionAnomalyRule,
  createVeeRule,
  deactivateConsumptionAnomalyRule,
  deactivateVeeRule,
  getApprovalLevels,
  getConsumptionAnomalyRules,
  getVeeRules,
} from "../api";
import { StagePage, EmptyState } from "../components/StagePage";

function SectionCard({ title, description, children }: { title: string; description: string; children: React.ReactNode }) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 mb-6">
      <h2 className="text-base font-semibold text-slate-900">{title}</h2>
      <p className="text-sm text-slate-500 mb-4">{description}</p>
      {children}
    </section>
  );
}

function VeeRulesSection() {
  const queryClient = useQueryClient();
  const { data } = useQuery({ queryKey: ["vee-rules"], queryFn: getVeeRules });
  const [type, setType] = useState<"range" | "missing_interval">("range");
  const [channel, setChannel] = useState("active_energy");
  const [min, setMin] = useState("0");
  const [max, setMax] = useState("999999");
  const [intervalSeconds, setIntervalSeconds] = useState("900");
  const [toleranceSeconds, setToleranceSeconds] = useState("60");
  const [error, setError] = useState<string | null>(null);

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["vee-rules"] });

  const createMutation = useMutation({
    mutationFn: () =>
      type === "range"
        ? createVeeRule({ type, params: { channel, min: Number(min), max: Number(max) }, priority: 100 })
        : createVeeRule({
            type,
            params: {
              channel,
              expected_interval_seconds: Number(intervalSeconds),
              tolerance_seconds: Number(toleranceSeconds),
              estimation_method: "linear_interpolation",
            },
            priority: 100,
          }),
    onSuccess: () => { setError(null); invalidate(); },
    onError: (err) => setError(err instanceof ApiError ? err.message : "No se pudo crear la regla."),
  });

  const deactivateMutation = useMutation({
    mutationFn: deactivateVeeRule,
    onSuccess: invalidate,
  });

  return (
    <SectionCard title="Reglas VEE" description="Rangos válidos e intervalos esperados por canal — usadas por el motor de validación en el siguiente pase.">
      <div className="flex flex-wrap items-end gap-3 mb-4">
        <div>
          <label className="block text-xs font-medium text-slate-500 mb-1">Tipo</label>
          <select className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm" value={type} onChange={(e) => setType(e.target.value as "range" | "missing_interval")}>
            <option value="range">Rango (min/max)</option>
            <option value="missing_interval">Intervalo esperado</option>
          </select>
        </div>
        <div>
          <label className="block text-xs font-medium text-slate-500 mb-1">Canal</label>
          <input className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm w-36" value={channel} onChange={(e) => setChannel(e.target.value)} />
        </div>
        {type === "range" ? (
          <>
            <div>
              <label className="block text-xs font-medium text-slate-500 mb-1">Mínimo</label>
              <input className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm w-28" value={min} onChange={(e) => setMin(e.target.value)} />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-500 mb-1">Máximo</label>
              <input className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm w-28" value={max} onChange={(e) => setMax(e.target.value)} />
            </div>
          </>
        ) : (
          <>
            <div>
              <label className="block text-xs font-medium text-slate-500 mb-1">Intervalo esperado (s)</label>
              <input className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm w-32" value={intervalSeconds} onChange={(e) => setIntervalSeconds(e.target.value)} />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-500 mb-1">Tolerancia (s)</label>
              <input className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm w-28" value={toleranceSeconds} onChange={(e) => setToleranceSeconds(e.target.value)} />
            </div>
          </>
        )}
        <button
          onClick={() => createMutation.mutate()}
          disabled={createMutation.isPending}
          className="rounded-lg bg-indigo-600 text-white text-sm font-semibold px-4 py-1.5 hover:bg-indigo-700 disabled:opacity-50"
        >
          Agregar
        </button>
      </div>
      {error && <p className="text-sm text-red-600 mb-3">{error}</p>}

      {data && data.length === 0 && <EmptyState message="Sin reglas VEE activas todavía." />}
      {data && data.length > 0 && (
        <ul className="divide-y divide-slate-100">
          {data.map((rule) => (
            <li key={rule.id} className="flex items-center justify-between py-2 text-sm">
              <span className="text-slate-700">
                <strong>{rule.type}</strong> — {JSON.stringify(rule.params)}
              </span>
              <button
                onClick={() => deactivateMutation.mutate(rule.id)}
                className="text-xs text-slate-400 hover:text-red-600"
              >
                Desactivar
              </button>
            </li>
          ))}
        </ul>
      )}
    </SectionCard>
  );
}

function ConsumptionAnomalyRulesSection() {
  const queryClient = useQueryClient();
  const { data } = useQuery({ queryKey: ["consumption-anomaly-rules"], queryFn: getConsumptionAnomalyRules });
  const [maxDeviationPct, setMaxDeviationPct] = useState("30");
  const [action, setAction] = useState<"reread_order" | "inspection_order">("reread_order");

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["consumption-anomaly-rules"] });
  const createMutation = useMutation({
    mutationFn: () => createConsumptionAnomalyRule({ condition: { max_deviation_pct: Number(maxDeviationPct) }, action }),
    onSuccess: invalidate,
  });
  const deactivateMutation = useMutation({ mutationFn: deactivateConsumptionAnomalyRule, onSuccess: invalidate });

  return (
    <SectionCard title="Reglas de desviación de consumo" description="Cuánto puede desviarse un consumo del período anterior antes de generar una orden.">
      <div className="flex flex-wrap items-end gap-3 mb-4">
        <div>
          <label className="block text-xs font-medium text-slate-500 mb-1">Desviación máxima (%)</label>
          <input className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm w-28" value={maxDeviationPct} onChange={(e) => setMaxDeviationPct(e.target.value)} />
        </div>
        <div>
          <label className="block text-xs font-medium text-slate-500 mb-1">Acción</label>
          <select className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm" value={action} onChange={(e) => setAction(e.target.value as "reread_order" | "inspection_order")}>
            <option value="reread_order">Orden de relectura</option>
            <option value="inspection_order">Orden de inspección</option>
          </select>
        </div>
        <button
          onClick={() => createMutation.mutate()}
          disabled={createMutation.isPending}
          className="rounded-lg bg-indigo-600 text-white text-sm font-semibold px-4 py-1.5 hover:bg-indigo-700 disabled:opacity-50"
        >
          Agregar
        </button>
      </div>

      {data && data.length === 0 && <EmptyState message="Sin reglas de anomalía activas todavía." />}
      {data && data.length > 0 && (
        <ul className="divide-y divide-slate-100">
          {data.map((rule) => (
            <li key={rule.id} className="flex items-center justify-between py-2 text-sm">
              <span className="text-slate-700">
                Desviación &gt; {String(rule.condition.max_deviation_pct)}% → <strong>{rule.action}</strong>
              </span>
              <button onClick={() => deactivateMutation.mutate(rule.id)} className="text-xs text-slate-400 hover:text-red-600">
                Desactivar
              </button>
            </li>
          ))}
        </ul>
      )}
    </SectionCard>
  );
}

function ApprovalLevelsSection() {
  const queryClient = useQueryClient();
  const { data } = useQuery({ queryKey: ["approval-levels"], queryFn: getApprovalLevels });
  const [orderType, setOrderType] = useState<"suspension" | "reconnection" | "disconnection">("suspension");
  const [requiresApproval, setRequiresApproval] = useState(true);
  const [role, setRole] = useState("supervisor");

  const createMutation = useMutation({
    mutationFn: () => createApprovalLevel({ order_type: orderType, requires_human_approval: requiresApproval, min_required_role: role }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["approval-levels"] }),
  });

  return (
    <SectionCard title="Niveles de aprobación de control (SCR)" description="Qué tipo de orden requiere aprobación humana y con qué rol. Crear una nueva versión reemplaza la anterior para ese tipo de orden.">
      <div className="flex flex-wrap items-end gap-3 mb-4">
        <div>
          <label className="block text-xs font-medium text-slate-500 mb-1">Tipo de orden</label>
          <select className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm" value={orderType} onChange={(e) => setOrderType(e.target.value as typeof orderType)}>
            <option value="suspension">Suspensión</option>
            <option value="reconnection">Reconexión</option>
            <option value="disconnection">Desconexión</option>
          </select>
        </div>
        <label className="flex items-center gap-2 text-sm text-slate-700">
          <input type="checkbox" checked={requiresApproval} onChange={(e) => setRequiresApproval(e.target.checked)} />
          Requiere aprobación humana
        </label>
        <div>
          <label className="block text-xs font-medium text-slate-500 mb-1">Rol mínimo</label>
          <input className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm w-32" value={role} onChange={(e) => setRole(e.target.value)} />
        </div>
        <button
          onClick={() => createMutation.mutate()}
          disabled={createMutation.isPending}
          className="rounded-lg bg-indigo-600 text-white text-sm font-semibold px-4 py-1.5 hover:bg-indigo-700 disabled:opacity-50"
        >
          Guardar
        </button>
      </div>

      {data && data.length === 0 && <EmptyState message="Sin niveles de aprobación configurados todavía." />}
      {data && data.length > 0 && (
        <ul className="divide-y divide-slate-100">
          {data.map((level) => (
            <li key={level.id} className="py-2 text-sm text-slate-700">
              <strong>{level.order_type}</strong>: {level.requires_human_approval ? `requiere aprobación de ${level.min_required_role}` : "auto-aprobada"}
            </li>
          ))}
        </ul>
      )}
    </SectionCard>
  );
}

export function ConfigurationPage() {
  return (
    <StagePage title="Configuración">
      <VeeRulesSection />
      <ConsumptionAnomalyRulesSection />
      <ApprovalLevelsSection />
    </StagePage>
  );
}
