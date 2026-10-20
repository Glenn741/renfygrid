import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ApiError,
  type FieldValue,
  type FormData,
  type FormEntry,
  type FormFieldDef,
  type GuideScope,
  type RecordFieldEntry,
} from "../api";
import { appLocale } from "../catalog";
import { Icon } from "./Icon";

// Fichas y tablas de las guias (Track E, 0047). Un solo editor para todas:
// los campos y columnas salen de la definicion del paquete
// (`form_spec`), nunca de una pantalla por formato. Se puede guardar a
// medias: la ficha queda en borrador hasta tener sus datos obligatorios.

const INPUT = "w-full rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 disabled:bg-slate-50";

function hasValue(v: FieldValue | undefined): boolean {
  if (v === null || v === undefined) return false;
  if (typeof v === "string") return v.trim() !== "";
  if (Array.isArray(v)) return v.length > 0;
  return true;
}

function GeoInput({ value, onChange, disabled, id }: { value: FieldValue; onChange: (v: FieldValue) => void; disabled: boolean; id: string }) {
  const point = value && typeof value === "object" && !Array.isArray(value) ? value : null;
  const [lat, setLat] = useState(point ? String(point.lat) : "");
  const [lon, setLon] = useState(point ? String(point.lon) : "");
  const [error, setError] = useState<string | null>(null);
  const commit = (la: string, lo: string) => {
    setLat(la);
    setLon(lo);
    const a = Number(la.replace(",", "."));
    const b = Number(lo.replace(",", "."));
    onChange(la.trim() && lo.trim() && Number.isFinite(a) && Number.isFinite(b) ? { lat: a, lon: b } : null);
  };
  const locate = () => {
    if (!navigator.geolocation) {
      setError("Este navegador no da la ubicación.");
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => { setError(null); commit(pos.coords.latitude.toFixed(6), pos.coords.longitude.toFixed(6)); },
      () => setError("No se pudo obtener la ubicación. Escríbala a mano."),
      { enableHighAccuracy: true, timeout: 15000 },
    );
  };
  return (
    <div>
      <div className="flex flex-wrap items-center gap-2">
        <input id={id} aria-label="Latitud" placeholder="Latitud (p. ej. -2.8974)" className={`${INPUT} max-w-[11rem]`} value={lat} disabled={disabled} onChange={(e) => commit(e.target.value, lon)} />
        <input aria-label="Longitud" placeholder="Longitud (p. ej. -78.7756)" className={`${INPUT} max-w-[11rem]`} value={lon} disabled={disabled} onChange={(e) => commit(lat, e.target.value)} />
        {!disabled && (
          <button type="button" onClick={locate} className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50">
            Usar mi ubicación
          </button>
        )}
      </div>
      {error && <p className="mt-1 text-xs text-amber-800">{error}</p>}
    </div>
  );
}

function ListInput({ value, onChange, disabled, id }: { value: FieldValue; onChange: (v: FieldValue) => void; disabled: boolean; id: string }) {
  const items = Array.isArray(value) ? value : [];
  const [text, setText] = useState(items.join("\n"));
  return (
    <textarea
      id={id}
      rows={Math.max(3, items.length + 1)}
      className={INPUT}
      placeholder="Una por línea"
      value={text}
      disabled={disabled}
      onChange={(e) => {
        setText(e.target.value);
        const lines = e.target.value.split("\n").map((l) => l.trim()).filter(Boolean);
        onChange(lines.length ? lines : null);
      }}
    />
  );
}

export function FieldInput({ def, value, onChange, disabled = false, id }: { def: FormFieldDef; value: FieldValue; onChange: (v: FieldValue) => void; disabled?: boolean; id: string }) {
  switch (def.type) {
    case "textarea":
      return <textarea id={id} rows={3} className={INPUT} value={typeof value === "string" ? value : ""} disabled={disabled} onChange={(e) => onChange(e.target.value)} />;
    case "integer":
    case "number":
      return (
        <input id={id} type="number" inputMode={def.type === "integer" ? "numeric" : "decimal"} min={def.signed ? undefined : 0} step={def.type === "integer" ? 1 : "any"}
          className={`${INPUT} max-w-[12rem]`} value={typeof value === "number" ? value : typeof value === "string" ? value : ""} disabled={disabled}
          onChange={(e) => onChange(e.target.value === "" ? null : Number(e.target.value))} />
      );
    case "date":
      return <input id={id} type="date" className={`${INPUT} max-w-[12rem]`} value={typeof value === "string" ? value : ""} disabled={disabled} onChange={(e) => onChange(e.target.value || null)} />;
    case "boolean":
      return (
        <select id={id} className={`${INPUT} max-w-[8rem]`} value={value === true ? "yes" : value === false ? "no" : ""} disabled={disabled}
          onChange={(e) => onChange(e.target.value === "" ? null : e.target.value === "yes")}>
          <option value="">—</option><option value="yes">Sí</option><option value="no">No</option>
        </select>
      );
    case "choice":
      return (
        <select id={id} className={INPUT} value={typeof value === "string" ? value : ""} disabled={disabled} onChange={(e) => onChange(e.target.value || null)}>
          <option value="">— Elegir —</option>
          {(def.options ?? []).map((o) => <option key={o.code} value={o.code}>{o.label}</option>)}
        </select>
      );
    case "multi": {
      const selected = Array.isArray(value) ? value : [];
      return (
        <div className="flex flex-wrap gap-2">
          {(def.options ?? []).map((o) => {
            const on = selected.includes(o.code);
            return (
              <label key={o.code} className={`inline-flex cursor-pointer items-center gap-1.5 rounded-lg border px-3 py-1.5 text-sm has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-indigo-500 ${on ? "border-indigo-600 bg-indigo-50 font-semibold text-indigo-800" : "border-slate-300 bg-white text-slate-700"}`}>
                <input type="checkbox" className="sr-only" checked={on} disabled={disabled}
                  onChange={() => { const next = on ? selected.filter((c) => c !== o.code) : [...selected, o.code]; onChange(next.length ? next : null); }} />
                {on && <Icon name="check" className="h-3.5 w-3.5" />}{o.label}
              </label>
            );
          })}
        </div>
      );
    }
    case "geo":
      return <GeoInput id={id} value={value} onChange={onChange} disabled={disabled} />;
    case "list":
      return <ListInput id={id} value={value} onChange={onChange} disabled={disabled} />;
    default:
      return <input id={id} className={INPUT} value={typeof value === "string" ? value : value === null || value === undefined ? "" : String(value)} disabled={disabled} onChange={(e) => onChange(e.target.value)} />;
  }
}

function StatusLine({ entry }: { entry: FormEntry }) {
  const p = entry.progress;
  return (
    <p className="text-xs text-slate-500">
      {entry.updated_at
        ? <>Guardado el {new Date(entry.updated_at).toLocaleString(appLocale())} por {entry.updated_by?.replace(/^portal:/, "")} · {entry.versions} versión{entry.versions === 1 ? "" : "es"}</>
        : "Todavía no se ha guardado."}
      {" · "}
      <span className={p.complete ? "font-semibold text-emerald-700" : "font-semibold text-amber-700"}>
        {p.complete ? "Completa" : p.missing_required.length ? `Falta: ${p.missing_required.join(", ")}` : "En borrador"}
      </span>
    </p>
  );
}

function RecordEditor({ entry, draft, setDraft, disabled }: { entry: FormEntry; draft: FormData; setDraft: (d: FormData) => void; disabled: boolean }) {
  const fields = entry.template.form_spec.fields ?? [];
  const values = draft.fields ?? {};
  const set = (key: string, patch: Partial<RecordFieldEntry>) =>
    setDraft({ fields: { ...values, [key]: { value: values[key]?.value ?? null, estimated: values[key]?.estimated ?? false, note: values[key]?.note ?? null, ...patch } } });
  return (
    <div className="divide-y divide-slate-100">
      {fields.map((f, idx) => {
        const id = `${entry.template.id}-${f.key}`;
        const current = values[f.key];
        const header = f.group && f.group !== fields[idx - 1]?.group ? f.group : null;
        const filled = hasValue(current?.value);
        return (
          <div key={f.key}>
            {header && <h3 className="bg-slate-50 px-5 py-2 text-xs font-semibold uppercase tracking-wide text-slate-500">{header}</h3>}
            <div className="grid gap-2 px-5 py-4 md:grid-cols-[minmax(0,16rem)_minmax(0,1fr)]">
              <label htmlFor={id} className="text-sm font-medium text-slate-800">
                {f.label}{f.required && <span className="text-red-600"> *</span>}
                {f.verify && <span className="mt-0.5 block text-xs font-normal text-slate-500">Dónde verificarlo: {f.verify}</span>}
                {f.platform_note && <span className="mt-0.5 block text-[11px] font-normal italic text-slate-400">{f.platform_note}</span>}
              </label>
              <div className="space-y-2">
                <FieldInput key={`${id}-${entry.updated_at ?? "new"}`} id={id} def={f} value={current?.value ?? null} disabled={disabled} onChange={(v) => set(f.key, { value: v })} />
                {f.type !== "list" && f.type !== "textarea" && (
                  <div className="flex flex-wrap items-center gap-3">
                    <label className={`inline-flex items-center gap-1.5 text-xs ${filled ? "text-slate-700" : "text-slate-400"}`}>
                      <input type="checkbox" checked={Boolean(current?.estimated)} disabled={disabled || !filled} onChange={(e) => set(f.key, { estimated: e.target.checked })} />
                      Dato estimado, por verificar
                    </label>
                    <input aria-label={`Nota sobre ${f.label}`} placeholder="Quién puede ayudar a conseguirlo / nota" disabled={disabled}
                      className="min-w-[14rem] flex-1 rounded-md border border-slate-200 px-2 py-1 text-xs" value={current?.note ?? ""}
                      onChange={(e) => set(f.key, { note: e.target.value || null })} />
                  </div>
                )}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function TableEditor({ entry, draft, setDraft, disabled }: { entry: FormEntry; draft: FormData; setDraft: (d: FormData) => void; disabled: boolean }) {
  const spec = entry.template.form_spec;
  const columns = spec.columns ?? [];
  const rows = draft.rows ?? [];
  const maxRows = spec.max_rows;
  const setCell = (i: number, key: string, v: FieldValue) => setDraft({ rows: rows.map((r, j) => (j === i ? { ...r, [key]: v } : r)) });
  return (
    <div className="p-5">
      {spec.personal_data && (
        <p className="mb-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
          Contiene datos personales: guárdelo solo en la organización, no lo publique completo ni lo comparta en grupos abiertos.
        </p>
      )}
      <div className="overflow-x-auto">
        <table className="w-full min-w-[40rem] text-sm">
          <thead>
            <tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wide text-slate-500">
              <th className="w-8 py-2 pr-2 font-semibold">#</th>
              {columns.map((c) => <th key={c.key} className="py-2 pr-2 font-semibold">{c.label}{c.required && <span className="text-red-600"> *</span>}</th>)}
              <th className="w-10" />
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i} className="border-b border-slate-100 align-top">
                <td className="py-2 pr-2 text-xs text-slate-400 tabular-nums">{i + 1}</td>
                {columns.map((c) => (
                  <td key={c.key} className="min-w-[9rem] py-2 pr-2">
                    <FieldInput id={`${entry.template.id}-${i}-${c.key}`} def={c} value={(r[c.key] as FieldValue) ?? null} disabled={disabled} onChange={(v) => setCell(i, c.key, v)} />
                  </td>
                ))}
                <td className="py-2">
                  {!disabled && (
                    <button type="button" aria-label={`Quitar la fila ${i + 1}`} title="Quitar fila" onClick={() => setDraft({ rows: rows.filter((_, j) => j !== i) })}
                      className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 hover:bg-red-50 hover:text-red-600">
                      <Icon name="close" className="h-4 w-4" />
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {!disabled && (!maxRows || rows.length < maxRows) && (
        <button type="button" onClick={() => setDraft({ rows: [...rows, {}] })} className="mt-3 rounded-lg border border-dashed border-indigo-300 px-3 py-1.5 text-sm font-medium text-indigo-700 hover:bg-indigo-50">
          + Agregar fila
        </button>
      )}
      {maxRows && <p className="mt-2 text-xs text-slate-500">Máximo {maxRows} filas.</p>}
    </div>
  );
}

function initialDraft(entry: FormEntry): FormData {
  if (entry.template.kind === "record") return { fields: { ...(entry.data.fields ?? {}) } };
  const rows = entry.data.rows ?? [];
  if (rows.length) return { rows: rows.map((r) => ({ ...r })) };
  const spec = entry.template.form_spec;
  if (spec.preset_rows?.length) return { rows: spec.preset_rows.map((r) => ({ ...(r as Record<string, FieldValue>) })) };
  return { rows: Array.from({ length: Math.max(spec.min_rows ?? 1, 1) }, () => ({})) };
}

function cleanDraft(entry: FormEntry, draft: FormData): FormData {
  if (entry.template.kind === "record") {
    const fields = Object.fromEntries(
      Object.entries(draft.fields ?? {}).filter(([, v]) => hasValue(v.value) || (v.note ?? "").trim() !== ""),
    );
    return { fields };
  }
  const preset = entry.template.form_spec.preset_rows ?? [];
  const rows = (draft.rows ?? []).filter((r) => {
    const filled = Object.fromEntries(Object.entries(r).filter(([, v]) => hasValue(v as FieldValue)));
    if (Object.keys(filled).length === 0) return false;
    // Una fila que solo trae el tema escrito por la guia (7F) no es un dato.
    return !preset.some((p) => JSON.stringify(p) === JSON.stringify(filled));
  });
  return { rows };
}

export function FormEditor({ scope, templateId, onClose, onSaved }: {
  scope: GuideScope; templateId: string; onClose: () => void; onSaved: (message: string) => void;
}) {
  const queryClient = useQueryClient();
  const { data: entry, isLoading } = useQuery({ queryKey: [...scope.key, "form", templateId], queryFn: () => scope.getForm(templateId) });
  return (
    <section className="rounded-xl border border-slate-200 bg-white">
      <div className="border-b border-slate-200 p-5">
        <button onClick={onClose} className="mb-2 text-sm font-medium text-indigo-700 hover:underline">← Volver a la guía</button>
        {isLoading || !entry ? <p className="text-sm text-slate-500">Cargando…</p> : (
          <>
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-600">{entry.template.kind === "record" ? "Ficha" : "Tabla"}</span>
              {entry.template.stage_code && <span className="rounded-full bg-indigo-50 px-2 py-0.5 text-[11px] font-semibold text-indigo-700">{entry.template.stage_code}</span>}
              <h2 className="text-base font-semibold text-slate-900">{entry.template.title}</h2>
            </div>
            <p className="mt-1 max-w-3xl text-sm text-slate-600">{entry.template.purpose}</p>
            <div className="mt-2"><StatusLine entry={entry} /></div>
          </>
        )}
      </div>
      {entry && (
        <EditorBody
          key={entry.updated_at ?? "new"}
          entry={entry}
          scope={scope}
          onSaved={(saved) => {
            queryClient.setQueryData([...scope.key, "form", templateId], saved);
            queryClient.invalidateQueries({ queryKey: scope.key });
            onSaved(`"${saved.template.title}" guardada${saved.progress.complete ? " y completa" : " como borrador"}.`);
          }}
        />
      )}
    </section>
  );
}

function EditorBody({ entry, scope, onSaved }: { entry: FormEntry; scope: GuideScope; onSaved: (saved: FormEntry) => void }) {
  const [draft, setDraft] = useState<FormData>(() => initialDraft(entry));
  const [error, setError] = useState<string | null>(null);
  const disabled = scope.readOnly !== null;
  const dirty = useMemo(() => JSON.stringify(cleanDraft(entry, draft)) !== JSON.stringify(cleanDraft(entry, initialDraft(entry))), [draft, entry]);
  const mutation = useMutation({
    mutationFn: () => scope.saveForm(entry.template.id, cleanDraft(entry, draft)),
    onSuccess: (saved) => { setError(null); onSaved(saved); },
    onError: (err) => setError(err instanceof ApiError ? err.message : "No se pudo guardar."),
  });
  return (
    <>
      {scope.readOnly && <p className="border-b border-amber-200 bg-amber-50 px-5 py-2 text-sm text-amber-900">{scope.readOnly}</p>}
      {entry.template.kind === "record"
        ? <RecordEditor entry={entry} draft={draft} setDraft={setDraft} disabled={disabled} />
        : <TableEditor entry={entry} draft={draft} setDraft={setDraft} disabled={disabled} />}
      {!disabled && (
        <div className="sticky bottom-0 z-20 flex flex-wrap items-center justify-end gap-3 rounded-b-xl border-t border-slate-200 bg-white/95 px-5 py-3 backdrop-blur">
          {error && <p className="mr-auto text-sm text-red-600">{error}</p>}
          {!error && <p className="mr-auto text-xs text-slate-500">Puede guardar a medias y seguir otro día.</p>}
          <button onClick={() => mutation.mutate()} disabled={mutation.isPending || !dirty}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700 disabled:bg-indigo-300">
            {mutation.isPending ? "Guardando…" : dirty ? "Guardar" : "Sin cambios"}
          </button>
        </div>
      )}
    </>
  );
}
