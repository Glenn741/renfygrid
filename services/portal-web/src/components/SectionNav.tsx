import { useEffect, useRef, useState } from "react";

// Navegacion interna de pagina -- pulido de usabilidad (2026-09-14), a
// pedido del usuario ("la navegacion dentro de cada menu no se ve
// intuitiva"). Grounded en estandar real, no un gusto propio: Nielsen
// Norman Group encuentra que una navegacion persistente/sticky es ~22%
// mas rapida de recorrer, y que una pagina larga SIN ella tiene 39% mas
// abandono al 50% de scroll (NN/g, "Anchors OK? Re-Assessing In-Page
// Links", https://www.nngroup.com/articles/in-page-links/). El patron de
// "Settings view" de SaaS empresarial (Stripe, Salesforce Setup) organiza
// secciones heterogeneas con una navegacion propia en vez de un scroll
// ciego -- aca se implementa como una barra de chips pegajosa (no un
// segundo sidebar: ya hay uno para las 12 pantallas de nivel superior,
// duplicarlo aqui competiria por el mismo espacio).
//
// Cada seccion objetivo necesita `id` + `scroll-mt-24` (o mayor) para que
// el propio header pegajoso de AppShell mas esta barra no tapen el titulo
// al saltar -- el mismo problema que NN/g documenta explicitamente para
// anchors bajo una barra sticky.

export interface SectionNavItem {
  id: string;
  label: string;
}

export function SectionNav({ items }: { items: SectionNavItem[] }) {
  const [active, setActive] = useState(items[0]?.id);
  const ticking = useRef(false);

  useEffect(() => {
    const onScroll = () => {
      if (ticking.current) return;
      ticking.current = true;
      requestAnimationFrame(() => {
        // El id "actual" es el ultimo cuyo titulo ya paso la linea de
        // referencia (justo debajo de esta barra) -- asi la barra refleja
        // en que seccion esta el usuario mientras hace scroll, no solo al
        // hacer click.
        const REFERENCE_Y = 120;
        let current = items[0]?.id;
        for (const item of items) {
          const el = document.getElementById(item.id);
          if (el && el.getBoundingClientRect().top <= REFERENCE_Y) current = item.id;
        }
        setActive(current);
        ticking.current = false;
      });
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
    return () => window.removeEventListener("scroll", onScroll);
  }, [items]);

  if (items.length < 2) return null;

  return (
    <div className="sticky top-14 z-20 -mx-4 lg:-mx-6 mb-6 border-b border-slate-200 bg-slate-50/95 backdrop-blur px-4 lg:px-6 py-2 flex gap-2 overflow-x-auto">
      {items.map((item) => (
        <button
          key={item.id}
          onClick={() => document.getElementById(item.id)?.scrollIntoView({ behavior: "smooth", block: "start" })}
          className={`shrink-0 rounded-full px-3 py-1 text-xs font-semibold border transition-colors ${
            active === item.id
              ? "bg-indigo-600 text-white border-indigo-600"
              : "bg-white text-slate-600 border-slate-200 hover:border-indigo-300 hover:text-indigo-700"
          }`}
        >
          {item.label}
        </button>
      ))}
    </div>
  );
}

// Helper de conveniencia: envuelve una seccion con el `id`+`scroll-mt`
// que SectionNav necesita, sin repetir la clase en cada pagina.
export function NavSection({ id, children }: { id: string; children: React.ReactNode }) {
  return (
    <div id={id} className="scroll-mt-24">
      {children}
    </div>
  );
}
