import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, createOrganization, getOrganizations, getPacks, getSectors, type TenantKind } from "../api";
import { AppShell } from "../components/AppShell";
import { EmptyState } from "../components/StagePage";
import { Icon } from "../components/Icon";
import { UsersRolesSection } from "./Configuration";
import { appLocale } from "../catalog";

// Organizaciones de la plataforma (Track E, 0047). Pedido del usuario: "es
// importante que se puedan crear usuarios nuevos y tenant nuevos". Solo la
// organizacion de tipo plataforma ve esta pantalla. Toda organizacion nace
// con el nucleo, los paquetes elegidos y un administrador; lo demas lo
// configura ella misma.

const KIND_LABEL: Record<TenantKind, string> = {
  provider: "Prestador (empresa, junta o comercializadora)",
  group: "Agrupación de prestadores",
  advisor: "ONG o entidad que asesora",
  platform: "Plataforma",
};

const INPUT = "w-full rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500";

export function OrganizationsPage() {
  const queryClient = useQueryClient();
  const { data: orgs, isLoading, error } = useQuery({ queryKey: ["organizations"], queryFn: getOrganizations });
  const { data: packs } = useQuery({ queryKey: ["packs"], queryFn: getPacks });
  const [form, setForm] = useState({ name: "", display_name: "", kind: "provider" as TenantKind, admin_username: "admin", admin_password: "", timezone: "", hours: "12" });
  const [chosen, setChosen] = useState<string[]>([]);
  // Track F (0048): energia, gas o agua (una multiservicio elige varios); el menu sale de aqui.
  const { data: sectorList } = useQuery({ queryKey: ["sectors"], queryFn: getSectors });
  const [sectors, setSectors] = useState<string[]>([]);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);
  const mutation = useMutation({
    mutationFn: () => createOrganization({
      name: form.name.trim().toLowerCase(), display_name: form.display_name || null, kind: form.kind,
      admin_username: form.admin_username.trim().toLowerCase(), admin_password: form.admin_password,
      timezone: form.timezone.trim() || null, session_ttl_seconds: Math.round(Number(form.hours) * 3600) || null, packs: chosen,
      sectors: form.kind === "platform" ? [] : sectors,
    }),
    onSuccess: (org) => {
      queryClient.invalidateQueries({ queryKey: ["organizations"] });
      setMessage({ ok: true, text: `Organización "${org.name}" creada. Entregue: organización ${org.name}, usuario ${org.admin.email} y la clave que escribió.` });
      setForm({ ...form, name: "", display_name: "", admin_password: "" });
    },
    onError: (err) => setMessage({ ok: false, text: err instanceof ApiError ? err.message : "No se pudo crear la organización." }),
  });
  const optional = (packs?.packs ?? []).filter((p) => p.kind !== "core");
  return (
    <AppShell title="Organizaciones">
      <div className="space-y-5">
        <section className="rounded-xl border border-slate-200 bg-white p-5">
          <h2 className="text-base font-semibold text-slate-900">Nueva organización</h2>
          <p className="mb-4 text-xs text-slate-500">Nace con el núcleo, los paquetes que elija y su usuario administrador. Zona horaria, moneda y región se heredan de esta organización si no se indican.</p>
          <div className="grid gap-3 md:grid-cols-3">
            <label className="text-sm font-medium text-slate-800">Código para iniciar sesión *
              <input className={`${INPUT} mt-1`} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="p. ej. jaas-sanjuan" />
            </label>
            <label className="text-sm font-medium text-slate-800">Nombre para mostrar
              <input className={`${INPUT} mt-1`} value={form.display_name} onChange={(e) => setForm({ ...form, display_name: e.target.value })} placeholder="p. ej. Junta de Agua San Juan" />
            </label>
            <label className="text-sm font-medium text-slate-800">Tipo *
              <select className={`${INPUT} mt-1`} value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value as TenantKind })}>
                {(Object.keys(KIND_LABEL) as TenantKind[]).map((k) => <option key={k} value={k}>{KIND_LABEL[k]}</option>)}
              </select>
            </label>
            <label className="text-sm font-medium text-slate-800">Usuario administrador *
              <input className={`${INPUT} mt-1`} value={form.admin_username} onChange={(e) => setForm({ ...form, admin_username: e.target.value })} />
            </label>
            <label className="text-sm font-medium text-slate-800">Clave inicial (mínimo 8) *
              <input type="password" autoComplete="new-password" className={`${INPUT} mt-1`} value={form.admin_password} onChange={(e) => setForm({ ...form, admin_password: e.target.value })} />
            </label>
            <div className="grid grid-cols-2 gap-3">
              <label className="text-sm font-medium text-slate-800">Sesión (horas)
                <input type="number" min={1} className={`${INPUT} mt-1`} value={form.hours} onChange={(e) => setForm({ ...form, hours: e.target.value })} />
              </label>
              <label className="text-sm font-medium text-slate-800">Zona horaria
                <input className={`${INPUT} mt-1`} value={form.timezone} onChange={(e) => setForm({ ...form, timezone: e.target.value })} placeholder="heredada" />
              </label>
            </div>
          </div>
          {form.kind !== "platform" && (
            <fieldset className="mt-3">
              <legend className="mb-1 text-sm font-medium text-slate-800">Sector que opera * <span className="font-normal text-slate-500">(define su menú; una empresa multiservicio elige varios)</span></legend>
              <div className="flex flex-wrap gap-2">
                {(sectorList ?? []).map((sc) => (
                  <label key={sc.code} title={sc.description} className={`inline-flex cursor-pointer items-center gap-1.5 rounded-lg border px-3 py-1.5 text-sm ${sectors.includes(sc.code) ? "border-indigo-600 bg-indigo-50 font-semibold text-indigo-800" : "border-slate-300 text-slate-700"}`}>
                    <input type="checkbox" className="sr-only" checked={sectors.includes(sc.code)} onChange={() => setSectors(sectors.includes(sc.code) ? sectors.filter((c) => c !== sc.code) : [...sectors, sc.code])} />
                    <Icon name={sc.icon} className="h-4 w-4" />{sc.label}
                  </label>
                ))}
              </div>
            </fieldset>
          )}
          {optional.length > 0 && (
            <fieldset className="mt-3">
              <legend className="mb-1 text-sm font-medium text-slate-800">Paquetes (país y programa)</legend>
              <div className="flex flex-wrap gap-2">
                {optional.map((p) => (
                  <label key={p.pack_id} className={`inline-flex cursor-pointer items-center gap-1.5 rounded-lg border px-3 py-1.5 text-sm ${chosen.includes(p.pack_id) ? "border-indigo-600 bg-indigo-50 font-semibold text-indigo-800" : "border-slate-300 text-slate-700"}`}>
                    <input type="checkbox" className="sr-only" checked={chosen.includes(p.pack_id)} onChange={() => setChosen(chosen.includes(p.pack_id) ? chosen.filter((c) => c !== p.pack_id) : [...chosen, p.pack_id])} />
                    {p.name}
                  </label>
                ))}
              </div>
            </fieldset>
          )}
          {message && <p className={`mt-3 text-sm ${message.ok ? "text-emerald-700" : "text-red-600"}`}>{message.text}</p>}
          <div className="mt-4 flex justify-end">
            <button className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700 disabled:bg-indigo-300"
              disabled={!form.name.trim() || !form.admin_username.trim() || form.admin_password.length < 8 || (form.kind !== "platform" && sectors.length === 0) || mutation.isPending} onClick={() => mutation.mutate()}>
              {mutation.isPending ? "Creando…" : "Crear organización"}
            </button>
          </div>
        </section>

        <section className="rounded-xl border border-slate-200 bg-white p-5">
          <h2 className="mb-3 text-base font-semibold text-slate-900">Organizaciones</h2>
          {isLoading && <p className="text-sm text-slate-500">Cargando…</p>}
          {error && <EmptyState message={error instanceof ApiError ? error.message : "No se pudo cargar."} />}
          {orgs && (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wide text-slate-500">
                    <th className="py-2 pr-3 font-semibold">Código</th>
                    <th className="py-2 pr-3 font-semibold">Nombre</th>
                    <th className="py-2 pr-3 font-semibold">Tipo</th>
                    <th className="py-2 pr-3 font-semibold">Creada</th>
                  </tr>
                </thead>
                <tbody>
                  {orgs.map((o) => (
                    <tr key={o.tenant_id} className="border-b border-slate-100 last:border-0">
                      <td className="py-2 pr-3 font-mono text-xs text-slate-800">{o.name}</td>
                      <td className="py-2 pr-3 text-slate-700">{o.display_name ?? "—"}</td>
                      <td className="py-2 pr-3 text-slate-700">{KIND_LABEL[o.kind] ?? o.kind}{!o.is_active && " (inactiva)"}</td>
                      <td className="py-2 pr-3 text-slate-500 tabular-nums">{new Date(o.created_at).toLocaleDateString(appLocale())}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>
    </AppShell>
  );
}

export function TeamPage() {
  return (
    <AppShell title="Usuarios">
      <UsersRolesSection />
    </AppShell>
  );
}
