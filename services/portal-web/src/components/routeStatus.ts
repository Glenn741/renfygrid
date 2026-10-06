import type { RouteStageInfo } from "../api";

// Estado visual de una etapa de la ruta, compartido por los pasos de la
// pantalla "Ruta y revisiones" y el submenu lateral, para que ambos digan lo
// mismo con los mismos colores.

export type StageState = "overdue" | "complete" | "started" | "pending" | "empty";

export function stageState(stage: RouteStageInfo): StageState {
  if (stage.summary.total === 0) return "empty";
  if (stage.summary.overdue > 0) return "overdue";
  if (stage.summary.applied === stage.summary.total) return "complete";
  if (stage.summary.applied > 0) return "started";
  return "pending";
}

export const STAGE_STATE_STYLE: Record<StageState, { badge: string; dot: string; label: string }> = {
  overdue: { badge: "bg-red-500 text-white", dot: "bg-red-500", label: "Tiene revisiones vencidas" },
  complete: { badge: "bg-emerald-600 text-white", dot: "bg-emerald-500", label: "Revisiones al día" },
  started: { badge: "bg-indigo-600 text-white", dot: "bg-indigo-400", label: "Revisiones en curso" },
  pending: { badge: "bg-slate-200 text-slate-700", dot: "bg-slate-400", label: "Revisiones sin aplicar" },
  empty: { badge: "bg-slate-200 text-slate-500", dot: "bg-slate-600", label: "Sin listas todavía" },
};

export const ROUTE_QUERY_KEY = ["process-route"] as const;
