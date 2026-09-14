// Extraido de Vee.tsx (2026-09-14, pulido de Vista general) para
// reutilizarlo tal cual en el tablero de Nivel 1 -- mismo grafico real de
// barras apiladas verde/rojo por dia, sin duplicar logica.
export function TrendBars({ trend }: { trend: { date: string; total: number; invalid: number }[] }) {
  const max = Math.max(1, ...trend.map((d) => d.total));
  return (
    <div className="flex items-end gap-2 h-20">
      {trend.map((d) => (
        <div key={d.date} className="flex-1 flex flex-col items-center gap-1" title={`${d.date}: ${d.invalid}/${d.total} inválidas`}>
          <div className="w-full flex flex-col justify-end h-14 rounded bg-slate-100 overflow-hidden">
            <div className="w-full bg-red-400" style={{ height: `${(d.invalid / max) * 100}%` }} />
            <div className="w-full bg-emerald-300" style={{ height: `${((d.total - d.invalid) / max) * 100}%` }} />
          </div>
          <span className="text-[10px] text-slate-400">{d.date.slice(5)}</span>
        </div>
      ))}
    </div>
  );
}
