import { Link } from "react-router-dom";
import type { ReactNode } from "react";

interface StagePageProps {
  title: string;
  children: ReactNode;
}

// Layout compartido de Nivel 2 -- header con vuelta al tablero general
// (Nivel 1), mismo patron en las 5 pantallas de etapa.
export function StagePage({ title, children }: StagePageProps) {
  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white px-6 py-4 flex items-center gap-4">
        <Link to="/" className="text-sm text-indigo-600 hover:text-indigo-700">
          ← Vista general
        </Link>
        <h1 className="text-lg font-bold text-slate-900">{title}</h1>
      </header>
      <main className="p-6">{children}</main>
    </div>
  );
}

export function EmptyState({ message }: { message: string }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-8 text-center text-sm text-slate-500">
      {message}
    </div>
  );
}
