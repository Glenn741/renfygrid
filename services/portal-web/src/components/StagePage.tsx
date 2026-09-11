import type { ReactNode } from "react";
import { AppShell } from "./AppShell";

interface StagePageProps {
  title: string;
  children: ReactNode;
}

// Layout compartido de Nivel 2 (Sprint C9: ahora delega en AppShell -- panel
// lateral con las 8 rutas de nivel superior siempre visible, en vez del link
// suelto "Vuelta al tablero" de antes). Ninguna de las 8 pantallas que usan
// StagePage cambio su logica -- solo el wrapper.
export function StagePage({ title, children }: StagePageProps) {
  return <AppShell title={title}>{children}</AppShell>;
}

export function EmptyState({ message }: { message: string }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-8 text-center text-sm text-slate-500">
      {message}
    </div>
  );
}
