import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ApiError,
  bulkMarkMeterProtection,
  createApprovalLevel,
  createConsumptionAnomalyRule,
  createProtocolMapping,
  createVeeRule,
  deactivateConsumptionAnomalyRule,
  deactivateVeeRule,
  getApprovalLevels,
  getConsumptionAnomalyRules,
  getProtectedMeters,
  getProtocolMappings,
  getVeeRules,
  markMeterProtection,
} from "../api";
import { StagePage, EmptyState } from "../components/StagePage";
import { NavSection, SectionNav } from "../components/SectionNav";

// Pulido de usabilidad (2026-09-14): esta era la pagina mas larga del
// portal -- 5 secciones de administracion sin ninguna relacion visual
// entre si, apiladas en un solo scroll ciego. Convertida al patron real
// de "Settings view" de SaaS empresarial (Stripe, Salesforce Setup: ver
// docs/05-ejecucion.md, pulido de navegacion) -- barra de secciones
// pegajosa arriba, cada `SectionCard` con su propio `id` para saltar
// directo.
const SECTIONS = [
  { id: "vee-rules", label: "Reglas VEE" },
  { id: "consumption-rules", label: "Reglas de consumo" },
  { id: "approval-levels", label: "Aprobación (SCR)" },
  { id: "protocol-mapping", label: "Mapeo OBIS" },
  { id: "protected-accounts", label: "Cuentas protegidas" },
];

function SectionCard({ title, description, children }: { title: string; description: string; children: React.ReactNode }) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5 mb-6">
      <h2 className="text-base font-semibold text-slate-900">{title}</h2>
      <p className="text-sm text-slate-500 mb-4">{description}</p>
      {children}
    </section>
  );
}

const ESTIMATION_METHODS = [
  { value: "linear_interpolation", label: "Interpolación lineal" },
  { value: "customer_historical_average", label: "Promedio histórico del medidor (misma hora del día)" },
  { value: "similar_customers_average", label: "Promedio de medidores similares (mismo instante)" },
] as const;

function VeeRulesSection() {
  const queryClient = useQueryClient();
  const { data } = useQuery({ queryKey: ["vee-rules"], queryFn: getVeeRules });
  const [type, setType] = useState<"range" | "missing_interval" | "channel_consistency">("range");
  const [channel, setChannel] = useState("active_energy");
  const [min, setMin] = useState("0");
  const [max, setMax] = useState("999999");
  const [intervalSeconds, setIntervalSeconds] = useState("900");
  const [toleranceSeconds, setToleranceSeconds] = useState("60");
  const [estimationMethod, setEstimationMethod] = useState<string>(ESTIMATION_METHODS[0].value);
  const [referenceChannel, setReferenceChannel] = useState("active_energy");
  const [minRatio, setMinRatio] = useState("0");
  const [maxRatio, setMaxRatio] = useState("1.0");
  const [error, setError] = useState<string | null>(null);

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["vee-rules"] });

  const createMutation = useMutation({
    mutationFn: () => {
      if (type === "range") {
        return createVeeRule({ type, params: { channel, min: Number(min), max: Number(max) }, priority: 100 });
      }
      if (type === "missing_interval") {
        return createVeeRule({
          type,
          params: {
            channel,
            expected_interval_seconds: Number(intervalSeconds),
            tolerance_seconds: Number(toleranceSeconds),
            estimation_method: estimationMethod,
          },
          priority: 100,
        });
      }
      // channel_consistency (Sprint C11): compara `channel` contra
      // `reference_channel` del mismo medidor en el mismo instante.
      return createVeeRule({
        type,
        params: { channel, reference_channel: referenceChannel, min_ratio: Number(minRatio), max_ratio: Number(maxRatio) },
        priority: 100,
      });
    },
    onSuccess: () => { setError(null); invalidate(); },
    onError: (err) => setError(err instanceof ApiError ? err.message : "No se pudo crear la regla."),
  });

  const deactivateMutation = useMutation({
    mutationFn: deactivateVeeRule,
    onSuccess: invalidate,
  });

  return (
    <SectionCard title="Reglas VEE" description="Rangos válidos, intervalos esperados y coherencia entre canales — usadas por el motor de validación/estimación en el siguiente pase.">
      <div className="flex flex-wrap items-end gap-3 mb-4">
        <div>
          <label className="block text-xs font-medium text-slate-500 mb-1">Tipo</label>
          <select
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm"
            value={type}
            onChange={(e) => setType(e.target.value as "range" | "missing_interval" | "channel_consistency")}
          >
            <option value="range">Rango (min/max)</option>
            <option value="missing_interval">Intervalo esperado (estimación)</option>
            <option value="channel_consistency">Coherencia entre canales</option>
          </select>
        </div>
        <div>
          <label className="block text-xs font-medium text-slate-500 mb-1">Canal</label>
          <input className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm w-36" value={channel} onChange={(e) => setChannel(e.target.value)} />
        </div>
        {type === "range" && (
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
        )}
        {type === "missing_interval" && (
          <>
            <div>
              <label className="block text-xs font-medium text-slate-500 mb-1">Intervalo esperado (s)</label>
              <input className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm w-32" value={intervalSeconds} onChange={(e) => setIntervalSeconds(e.target.value)} />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-500 mb-1">Tolerancia (s)</label>
              <input className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm w-28" value={toleranceSeconds} onChange={(e) => setToleranceSeconds(e.target.value)} />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-500 mb-1">Método de estimación</label>
              <select className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm" value={estimationMethod} onChange={(e) => setEstimationMethod(e.target.value)}>
                {ESTIMATION_METHODS.map((m) => (
                  <option key={m.value} value={m.value}>{m.label}</option>
                ))}
              </select>
            </div>
          </>
        )}
        {type === "channel_consistency" && (
          <>
            <div>
              <label className="block text-xs font-medium text-slate-500 mb-1">Canal de referencia</label>
              <input className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm w-36" value={referenceChannel} onChange={(e) => setReferenceChannel(e.target.value)} />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-500 mb-1">Ratio mínimo</label>
              <input className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm w-24" value={minRatio} onChange={(e) => setMinRatio(e.target.value)} />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-500 mb-1">Ratio máximo</label>
              <input className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm w-24" value={maxRatio} onChange={(e) => setMaxRatio(e.target.value)} />
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
      {type === "channel_consistency" && (
        <p className="text-xs text-slate-500 mb-3">
          Compara "{channel}" contra "{referenceChannel}" del mismo medidor en el mismo instante — si el canal de
          referencia no reportó en ese instante, la lectura pasa sin evaluar (nunca se inventa un ratio).
        </p>
      )}
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

function ProtocolMappingSection() {
  const queryClient = useQueryClient();
  const { data } = useQuery({ queryKey: ["protocol-mappings"], queryFn: getProtocolMappings });
  const [brand, setBrand] = useState("");
  const [model, setModel] = useState("");
  const [protocol, setProtocol] = useState("DLMS_COSEM");
  const [channel, setChannel] = useState("active_energy");
  const [obisCode, setObisCode] = useState("1.0.1.8.0.255");
  const [attributeIndex, setAttributeIndex] = useState("2");
  const [error, setError] = useState<string | null>(null);

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["protocol-mappings"] });

  // Agregar un canal no reemplaza los demas de esa marca/modelo: si ya hay
  // una version activa, se parte de su obis_mapping y solo se agrega/edita
  // el canal del formulario -- el backend sigue cerrando la version vieja y
  // creando una nueva (mismo patron que ApprovalLevel), pero desde aca nunca
  // se manda un mapeo a medias por accidente.
  const existing = data?.find((m) => m.brand === brand && m.model === model);

  const createMutation = useMutation({
    mutationFn: () =>
      createProtocolMapping({
        brand,
        model,
        protocol,
        obis_mapping: {
          ...(existing?.obis_mapping ?? {}),
          [channel]: { obis_code: obisCode, attribute_index: Number(attributeIndex) },
        },
      }),
    onSuccess: () => { setError(null); invalidate(); },
    onError: (err) => setError(err instanceof ApiError ? err.message : "No se pudo guardar el mapeo."),
  });

  return (
    <SectionCard
      title="Mapeo OBIS por marca/modelo"
      description="Qué código OBIS lee el poller para cada canal, según la marca/modelo del medidor. Guardar agrega o reemplaza un canal y crea una nueva versión — el siguiente ciclo del poller ya la usa, sin tocar código."
    >
      <div className="flex flex-wrap items-end gap-3 mb-4">
        <div>
          <label className="block text-xs font-medium text-slate-500 mb-1">Marca</label>
          <input className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm w-32" value={brand} onChange={(e) => setBrand(e.target.value)} />
        </div>
        <div>
          <label className="block text-xs font-medium text-slate-500 mb-1">Modelo</label>
          <input className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm w-32" value={model} onChange={(e) => setModel(e.target.value)} />
        </div>
        <div>
          <label className="block text-xs font-medium text-slate-500 mb-1">Protocolo</label>
          <input className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm w-32" value={protocol} onChange={(e) => setProtocol(e.target.value)} />
        </div>
        <div>
          <label className="block text-xs font-medium text-slate-500 mb-1">Canal</label>
          <input className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm w-36" value={channel} onChange={(e) => setChannel(e.target.value)} />
        </div>
        <div>
          <label className="block text-xs font-medium text-slate-500 mb-1">Código OBIS</label>
          <input className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm w-36" value={obisCode} onChange={(e) => setObisCode(e.target.value)} />
        </div>
        <div>
          <label className="block text-xs font-medium text-slate-500 mb-1">Índice de atributo</label>
          <input className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm w-24" value={attributeIndex} onChange={(e) => setAttributeIndex(e.target.value)} />
        </div>
        <button
          onClick={() => createMutation.mutate()}
          disabled={createMutation.isPending || !brand || !model}
          className="rounded-lg bg-indigo-600 text-white text-sm font-semibold px-4 py-1.5 hover:bg-indigo-700 disabled:opacity-50"
        >
          Guardar
        </button>
      </div>
      {error && <p className="text-sm text-red-600 mb-3">{error}</p>}
      {existing && (
        <p className="text-xs text-slate-500 mb-3">
          {brand}/{model} ya tiene una versión activa (v{existing.version}) — este canal se agrega o reemplaza ahí, los demás canales se conservan.
        </p>
      )}

      {data && data.length === 0 && <EmptyState message="Sin mapeos OBIS configurados todavía." />}
      {data && data.length > 0 && (
        <ul className="divide-y divide-slate-100">
          {data.map((mapping) => (
            <li key={mapping.id} className="py-2 text-sm text-slate-700">
              <strong>{mapping.brand} / {mapping.model}</strong>
              <span className="text-slate-400"> ({mapping.protocol}, v{mapping.version})</span>
              <div className="mt-1 flex flex-wrap gap-1.5">
                {Object.entries(mapping.obis_mapping).map(([ch, m]) => (
                  <span key={ch} className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600">
                    {ch} → {m.obis_code} (attr {m.attribute_index})
                  </span>
                ))}
              </div>
            </li>
          ))}
        </ul>
      )}
    </SectionCard>
  );
}

function ProtectedAccountsSection() {
  const queryClient = useQueryClient();
  const { data } = useQuery({ queryKey: ["protected-meters"], queryFn: getProtectedMeters });
  const [manualText, setManualText] = useState("");
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<{ marked: string[]; not_found: string[] } | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["protected-meters"] });

  const bulkMutation = useMutation({
    mutationFn: (accountNumbers: string[]) => bulkMarkMeterProtection({ account_numbers: accountNumbers, reason }),
    onSuccess: (res) => { setError(null); setResult(res); invalidate(); },
    onError: (err) => setError(err instanceof ApiError ? err.message : "No se pudo cargar la lista."),
  });

  const unmarkMutation = useMutation({
    mutationFn: (meterId: string) => markMeterProtection(meterId, { protected: false }),
    onSuccess: invalidate,
  });

  const parseAccountNumbers = (text: string): string[] =>
    text.split(/[\n,;]+/).map((s) => s.trim()).filter(Boolean);

  const handleManualSubmit = () => {
    const accounts = parseAccountNumbers(manualText);
    if (accounts.length === 0 || !reason) return;
    bulkMutation.mutate(accounts);
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !reason) return;
    const reader = new FileReader();
    reader.onload = () => {
      const accounts = parseAccountNumbers(String(reader.result ?? ""));
      if (accounts.length > 0) bulkMutation.mutate(accounts);
    };
    reader.readAsText(file);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  return (
    <SectionCard
      title="Cuentas protegidas contra suspensión/desconexión"
      description="Contratos que la regulación vigente (en Colombia, Ley 142 y normas de la CRA/CREG) excluye de corte -- hospitales, colegios, etc. RenfyGrid solo guarda la bandera de exclusión + quién/cuándo/por qué la marcó; la clasificación real del cliente vive en el CIS."
    >
      <div className="flex flex-wrap items-end gap-3 mb-4">
        <div className="flex-1 min-w-[240px]">
          <label className="block text-xs font-medium text-slate-500 mb-1">
            Cuentas a proteger (una por línea, o separadas por coma)
          </label>
          <textarea
            className="w-full rounded-lg border border-slate-300 px-3 py-1.5 text-sm"
            rows={3}
            value={manualText}
            onChange={(e) => setManualText(e.target.value)}
            placeholder={"ACC-0001\nACC-0002"}
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-slate-500 mb-1">Motivo (obligatorio)</label>
          <input
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm w-56"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Hospital / colegio / Ley 142..."
          />
        </div>
        <button
          onClick={handleManualSubmit}
          disabled={bulkMutation.isPending || !reason || parseAccountNumbers(manualText).length === 0}
          className="rounded-lg bg-indigo-600 text-white text-sm font-semibold px-4 py-1.5 hover:bg-indigo-700 disabled:opacity-50"
        >
          Marcar protegidas
        </button>
        <div>
          <label className="block text-xs font-medium text-slate-500 mb-1">o cargar un archivo (.csv/.txt)</label>
          <input
            ref={fileInputRef}
            type="file"
            accept=".csv,.txt"
            disabled={!reason}
            onChange={handleFileChange}
            className="text-sm text-slate-600 disabled:opacity-50"
          />
        </div>
      </div>
      {!reason && <p className="text-xs text-amber-700 mb-3">Escribe primero el motivo -- no se marca ninguna cuenta sin uno.</p>}
      {error && <p className="text-sm text-red-600 mb-3">{error}</p>}
      {result && (
        <p className="text-sm mb-3">
          <span className="text-emerald-700">{result.marked.length} marcada(s)</span>
          {result.not_found.length > 0 && (
            <span className="text-red-600"> — {result.not_found.length} cuenta(s) no encontrada(s): {result.not_found.join(", ")}</span>
          )}
        </p>
      )}

      {data && data.length === 0 && <EmptyState message="Sin cuentas protegidas todavía." />}
      {data && data.length > 0 && (
        <ul className="divide-y divide-slate-100">
          {data.map((row) => (
            <li key={row.meter_id} className="flex items-center justify-between py-2 text-sm">
              <span className="text-slate-700">
                <strong>{row.account_number}</strong> — {row.reason ?? "sin motivo registrado"}
                <span className="text-slate-400"> (marcada por {row.marked_by ?? "?"})</span>
              </span>
              <button
                onClick={() => unmarkMutation.mutate(row.meter_id)}
                disabled={unmarkMutation.isPending}
                className="text-xs text-slate-400 hover:text-red-600"
              >
                Quitar protección
              </button>
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
      <SectionNav items={SECTIONS} />
      <NavSection id="vee-rules"><VeeRulesSection /></NavSection>
      <NavSection id="consumption-rules"><ConsumptionAnomalyRulesSection /></NavSection>
      <NavSection id="approval-levels"><ApprovalLevelsSection /></NavSection>
      <NavSection id="protocol-mapping"><ProtocolMappingSection /></NavSection>
      <NavSection id="protected-accounts"><ProtectedAccountsSection /></NavSection>
    </StagePage>
  );
}
