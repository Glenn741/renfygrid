import {
  Activity, ArrowLeft, Building2, ChartLine, Check, ChevronDown, ChevronRight, CircleCheck, ClipboardCheck, Droplets, FileCheck2,
  FlaskConical, Gauge, House, Link2, ListChecks, Map, Menu, Minus, Network, NotebookPen, Package, Power, RadioTower, Recycle,
  Settings, Siren, Target, TriangleAlert, Users, Waves, Wrench, X, type LucideIcon,
} from "lucide-react";

// Iconos SVG de linea (mismo estilo del set corporativo: trazo 2, extremos
// redondeados, color del texto). Se nombran por su significado, no por su
// dibujo, para poder cambiar el dibujo sin tocar las pantallas.
const ICONS: Record<string, LucideIcon> = {
  overview: House,
  operations: Gauge,
  system: Network,
  quality: FlaskConical,
  emergencies: Siren,
  warehouse: Package,
  sanitation: Recycle,
  improvement: Target,
  report: FileCheck2,
  inspections: ClipboardCheck,
  maintenance: Wrench,
  metering: RadioTower,
  validation: ListChecks,
  consumption: ChartLine,
  control: Power,
  balance: Droplets,
  twin: Map,
  model: Waves,
  group: Users,
  observations: NotebookPen,
  integrations: Link2,
  observability: Activity,
  settings: Settings,
  organization: Building2,
  menu: Menu,
  expand: ChevronRight,
  dropdown: ChevronDown,
  alert: TriangleAlert,
  check: Check,
  ok: CircleCheck,
  close: X,
  partial: Minus,
  back: ArrowLeft,
};

export type IconName = keyof typeof ICONS;

export function Icon({ name, className = "h-4 w-4", label }: { name: string; className?: string; label?: string }) {
  const Svg = ICONS[name];
  if (!Svg) return null;
  return <Svg className={className} strokeWidth={2} aria-hidden={label ? undefined : true} aria-label={label} role={label ? "img" : undefined} />;
}
