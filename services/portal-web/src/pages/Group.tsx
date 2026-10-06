import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ApiError, type GroupIndicator, type GroupMembership, decideGroupMembership, getGroup, getGroupDashboard,
  inviteGroupMember, removeGroupMember, setOrganizationKind,
} from "../api";
import { StagePage, EmptyState } from "../components/StagePage";
import { badgeClass, label as codeLabel, appLocale, term, money } from "../catalog";

// Agrupación de juntas (Track D, D12.1). La agrupación solo ve lo que cada
// junta decidió compartir; la junta puede cambiarlo o salir cuando quiera.


function errText(err: unknown, fallback: string) {
  return err instanceof ApiError ? err.message : fallback;
}

function Card({ title, description, children }: { title: string; description?: string; children: React.ReactNode }) {
  return (
    <section className="mb-6 rounded-xl border border-slate-200 bg-white p-5">
      <h2 className="text-base font-semibold text-slate-900">{title}</h2>
      {description && <p className="mb-3 mt-1 max-w-3xl text-sm text-slate-600">{description}</p>}
      {children}
    </section>
  );
}

function Badge({ status }: { status: string }) {
  const s = { label: codeLabel("membership.status", status), cls: badgeClass("membership.status", status) };
  return <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${s.cls}`}>{s.label}</span>;
}

function Kpi({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div className="rounded-lg border border-slate-200 p-3">
      <p className="text-xs text-slate-500">{label}</p>
      <p className="text-xl font-semibold text-slate-900">{value}</p>
      {note && <p className="text-[11px] text-slate-500">{note}</p>}
    </div>
  );
}

function pct(v: number | null | undefined) {
  return v === null || v === undefined ? "—" : `${v.toLocaleString(appLocale())} %`;
}

function base(n: number, total: number) {
  return `${n} de ${total} ${term("provider", { plural: true })} lo comparten`;
}

function Dashboard() {
  const { data, error } = useQuery({ queryKey: ["group-dashboard"], queryFn: getGroupDashboard, retry: false });
  if (error) return <Card title="Tablero de la agrupación"><p className="text-sm text-amber-800">{errText(error, "")}</p></Card>;
  if (!data) return null;
  const r = data.rollup;
  const labels = Object.fromEntries(data.indicators.map((i) => [i.code, i.label]));
  return (
    <Card title="Tablero de la agrupación"
      description={`Solo miembros que aceptaron y solo los indicadores que cada uno decidió compartir. Lea cada total con su base: cuántos lo comparten.`}>
      <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-4">
        <Kpi label={`${term("provider", { plural: true, capital: true })} miembro`} value={String(r.members)} note={data.pending_invitations ? `${data.pending_invitations} invitaciones pendientes` : undefined} />
        <Kpi label="Alertas de calidad abiertas" value={String(r.quality_alerts.open)}
          note={`${r.quality_alerts.critical} críticas · ${base(r.quality_alerts.shared_by, r.members)}`} />
        <Kpi label="Cumplimiento del calendario" value={pct(r.calendar.average_pct)}
          note={`promedio; el más bajo ${pct(r.calendar.lowest_pct)} · ${base(r.calendar.shared_by, r.members)}`} />
        <Kpi label="Productos finales completos" value={`${r.products.complete} / ${r.products.total}`} note={base(r.products.shared_by, r.members)} />
        <Kpi label="Cambio del índice de madurez" value={r.maturity.average_change === null ? "—" : `${r.maturity.average_change > 0 ? "+" : ""}${r.maturity.average_change} pts`}
          note={`${r.maturity.evaluations_with_progress} verificaciones repetidas · ${base(r.maturity.shared_by, r.members)}`} />
        <Kpi label="Insumos para el Plan de Mejora" value={String(r.improvement.inputs)}
          note={`${money(r.improvement.cost_estimate_total)} estimados · ${r.improvement.to_quote} por cotizar`} />
        <Kpi label="Lodos vencidos / descargas abiertas" value={`${r.sanitation.sludge_overdue} / ${r.sanitation.open_discharges}`} note={base(r.sanitation.shared_by, r.members)} />
        <Kpi label="Emergencias activas" value={String(r.emergencies.active)} note={base(r.emergencies.shared_by, r.members)} />
      </div>
      <p className="mt-2 text-xs text-slate-500">
        {data.indicators.filter((i) => !i.available).map((i) => `${i.label}: ${i.unavailable_note}`).join(" ")}
      </p>
      <h3 className="mt-5 text-sm font-semibold text-slate-900">Por {term("provider")}</h3>
      {data.members.length === 0 ? <EmptyState message="Todavía no hay miembros que hayan aceptado." /> : (
        <div className="mt-2 space-y-3">
          {data.members.map((m) => {
            const ind = m.indicators;
            return (
              <article key={m.member_tenant_id} className="rounded-lg border border-slate-200 p-3 text-sm">
                <h4 className="font-semibold text-slate-900">{m.name}</h4>
                <p className="text-xs text-slate-500">Comparte: {m.shared.map((c) => labels[c] ?? c).join(", ")}</p>
                <ul className="mt-1 space-y-0.5 text-slate-700">
                  {ind.quality_alerts && <li>Alertas de calidad: {ind.quality_alerts.open} abiertas{ind.quality_alerts.critical ? `, ${ind.quality_alerts.critical} críticas` : ""}</li>}
                  {ind.calendar && <li>Calendario: {pct(ind.calendar.compliance_pct)}{ind.calendar.note ? ` (${ind.calendar.note})` : ""}</li>}
                  {ind.products && <li>Productos finales: {ind.products.complete} de {ind.products.total}</li>}
                  {ind.improvement && <li>Plan de Mejora: {ind.improvement.inputs} problemas, {money(ind.improvement.cost_estimate_total)}</li>}
                  {ind.sanitation && <li>Saneamiento: {ind.sanitation.sludge_overdue} lodos vencidos, {ind.sanitation.open_discharges} descargas abiertas</li>}
                  {ind.emergencies && <li>Emergencias activas: {ind.emergencies.active}</li>}
                  {ind.maturity && (ind.maturity.length === 0 ? <li>Madurez: sin verificaciones aplicadas</li>
                    : ind.maturity.map((t) => <li key={t.template_id}>{t.title}: {pct(t.initial_pct)} → {pct(t.current_pct)}</li>))}
                </ul>
              </article>
            );
          })}
        </div>
      )}
    </Card>
  );
}

function Members({ members }: { members: GroupMembership[] }) {
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const refresh = () => { qc.invalidateQueries({ queryKey: ["group"] }); qc.invalidateQueries({ queryKey: ["group-dashboard"] }); };
  const invite = useMutation({
    mutationFn: () => inviteGroupMember(name),
    onSuccess: () => { setName(""); setMsg(null); refresh(); },
    onError: (e) => setMsg(errText(e, "No se pudo invitar.")),
  });
  const remove = useMutation({ mutationFn: removeGroupMember, onSuccess: refresh, onError: (e) => setMsg(errText(e, "No se pudo retirar.")) });
  return (
    <Card title={`${term("provider", { plural: true, capital: true })} de la agrupación`} description={`Se invita por el nombre de la organización (el mismo que usa para entrar). Cada ${term("provider")} decide si acepta y qué comparte.`}>
      {members.length === 0 && <EmptyState message={`Todavía no ha invitado ${term("provider", { plural: true })}.`} />}
      <ul className="divide-y divide-slate-100">
        {members.map((m) => (
          <li key={m.member_tenant_id} className="flex flex-wrap items-center gap-3 py-2 text-sm">
            <span className="flex-1 text-slate-800">{m.name}</span>
            <Badge status={m.status} />
            {(m.status === "invited" || m.status === "accepted") && (
              <button onClick={() => remove.mutate(m.member_tenant_id)} className="text-xs text-slate-500 hover:text-red-600">Retirar</button>
            )}
          </li>
        ))}
      </ul>
      <div className="mt-3 flex flex-wrap gap-2">
        <input aria-label="Nombre de la organización" className="min-w-[14rem] flex-1 rounded-lg border border-slate-300 px-3 py-1.5 text-sm" placeholder="Nombre de la organización (el mismo que usa para entrar)" value={name} onChange={(e) => setName(e.target.value)} />
        <button onClick={() => invite.mutate()} disabled={!name.trim()} className="rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-semibold text-white disabled:opacity-50">Invitar</button>
      </div>
      {msg && <p className="mt-1 text-sm text-red-600">{msg}</p>}
    </Card>
  );
}

function MembershipCard({ m, indicators }: { m: GroupMembership; indicators: GroupIndicator[] }) {
  const qc = useQueryClient();
  const [shared, setShared] = useState<string[]>(m.shared);
  const [msg, setMsg] = useState<string | null>(null);
  const decide = useMutation({
    mutationFn: (action: string) => decideGroupMembership(m.group_tenant_id, action, action === "accept" || action === "share" ? shared : []),
    onSuccess: () => { setMsg(null); qc.invalidateQueries({ queryKey: ["group"] }); },
    onError: (e) => setMsg(errText(e, "No se pudo guardar.")),
  });
  const open = m.status === "invited" || m.status === "accepted";
  return (
    <article className="rounded-lg border border-slate-200 p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-slate-900">{m.name}</h3>
        <Badge status={m.status} />
      </div>
      <p className="text-xs text-slate-500">Invitó {m.invited_by.replace(/^portal:/, "")} el {new Date(m.invited_at).toLocaleDateString(appLocale())}
        {m.decided_by && ` · decidió ${m.decided_by.replace(/^portal:/, "")}`}</p>
      {open && (
        <>
          <p className="mt-2 text-xs font-medium text-slate-700">Qué comparte con esta agrupación:</p>
          <div className="mt-1 grid gap-1 sm:grid-cols-2">
            {indicators.map((i) => (
              <label key={i.code} className={`flex items-start gap-2 text-xs ${i.available ? "text-slate-700" : "text-slate-400"}`} title={i.unavailable_note ?? i.description}>
                <input type="checkbox" disabled={!i.available} checked={shared.includes(i.code)}
                  onChange={(e) => setShared(e.target.checked ? [...shared, i.code] : shared.filter((c) => c !== i.code))} />
                <span><strong>{i.label}</strong> — {i.available ? i.description : i.unavailable_note}</span>
              </label>
            ))}
          </div>
          <div className="mt-2 flex flex-wrap gap-2">
            {m.status === "invited" ? (
              <>
                <button onClick={() => decide.mutate("accept")} disabled={shared.length === 0} className="rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-semibold text-white disabled:opacity-50">Aceptar y compartir</button>
                <button onClick={() => decide.mutate("decline")} className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm text-slate-700">Rechazar</button>
              </>
            ) : (
              <>
                <button onClick={() => decide.mutate("share")} disabled={shared.length === 0} className="rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-semibold text-white disabled:opacity-50">Guardar lo que comparto</button>
                <button onClick={() => decide.mutate("leave")} className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm text-slate-700">Salir de la agrupación</button>
              </>
            )}
          </div>
        </>
      )}
      {msg && <p className="mt-1 text-sm text-red-600">{msg}</p>}
    </article>
  );
}

export function GroupPage() {
  const qc = useQueryClient();
  const { data, error } = useQuery({ queryKey: ["group"], queryFn: getGroup, retry: false });
  const [msg, setMsg] = useState<string | null>(null);
  const kind = useMutation({
    mutationFn: setOrganizationKind,
    onSuccess: () => { setMsg(null); qc.invalidateQueries({ queryKey: ["group"] }); },
    onError: (e) => setMsg(errText(e, "No se pudo cambiar.")),
  });
  if (error) return <StagePage title="Agrupación"><p className="text-sm text-amber-800">{errText(error, "")}</p></StagePage>;
  if (!data) return <StagePage title="Agrupación"><p className="text-sm text-slate-500">Cargando…</p></StagePage>;
  const isGroup = data.organization.kind === "group";
  return (
    <StagePage title={isGroup ? `Agrupación ${data.organization.name}` : "Agrupaciones"}>
      {isGroup ? (
        <>
          <Dashboard />
          <Members members={data.members} />
        </>
      ) : (
        <Card title="Agrupaciones"
          description="Una asociación, mancomunidad o programa puede invitarle a compartir técnico, compras o laboratorio. Usted decide qué indicadores ve la agrupación; nunca ve sus datos operativos y puede salir cuando quiera.">
          {data.groups.length === 0 ? <EmptyState message="No hay invitaciones." />
            : <div className="space-y-3">{data.groups.map((m) => <MembershipCard key={`${m.group_tenant_id}:${m.status}`} m={m} indicators={data.indicators} />)}</div>}
        </Card>
      )}
      {(isGroup ? data.members.length === 0 : data.groups.every((g) => g.status !== "invited" && g.status !== "accepted")) && (
        <p className="text-xs text-slate-500">
          {isGroup ? "¿Esta organización no es una agrupación?" : `¿Esta organización es una asociación o programa que agrupa ${term("provider", { plural: true })}?`}
          <button onClick={() => kind.mutate(isGroup ? "provider" : "group")} className="ml-2 font-semibold text-indigo-700 hover:underline">
            {isGroup ? "Volver a organización prestadora" : "Declararla agrupación"}
          </button>
          {msg && <span className="ml-2 text-red-600">{msg}</span>}
        </p>
      )}
    </StagePage>
  );
}
