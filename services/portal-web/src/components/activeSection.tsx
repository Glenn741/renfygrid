import { createContext, useContext, useState, type ReactNode } from "react";

// Seccion visible de la pantalla actual, compartida entre la barra de
// secciones de la pagina (que la detecta con el scroll) y el submenu lateral
// (que la resalta). Un solo estado: los dos siempre marcan lo mismo.

interface ActiveSectionValue {
  active: string | undefined;
  setActive: (id: string | undefined) => void;
}

const ActiveSectionContext = createContext<ActiveSectionValue>({ active: undefined, setActive: () => {} });

export function ActiveSectionProvider({ children }: { children: ReactNode }) {
  const [active, setActive] = useState<string | undefined>();
  return <ActiveSectionContext.Provider value={{ active, setActive }}>{children}</ActiveSectionContext.Provider>;
}

export function useActiveSection(): ActiveSectionValue {
  return useContext(ActiveSectionContext);
}

/** Lleva la seccion a la vista, dejando espacio para el encabezado fijo. */
export function scrollToSection(id: string): boolean {
  const el = document.getElementById(id);
  if (!el) return false;
  el.scrollIntoView({ behavior: "smooth", block: "start" });
  return true;
}
