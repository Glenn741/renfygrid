# Planteamiento — Producto MDM/AMI para el portafolio rensoftlabs.com

**Nombre comercial:** `RenfyGrid` (confirmado 2026-09-10, ver `00-benchmark-industria.md`
para el análisis competitivo que acompaña este planteamiento).
**Fecha:** 2026-09-09 (actualizado 2026-09-10) · **Estado:** Fase 1 de 4 (Planteamiento → Arquitectura → Diseño → Plan de sprints)

---

## 1. Contexto

La idea de este producto es del usuario, no de un tercero: viene desarrollándola desde hace
varios años. En 2024 la materializó en una propuesta comercial completa (arquitectura de
10 capas del modelo "Meter To Cash", proceso VEE, prototipo con historias de usuario) para
tres empresas de energía en Colombia interesadas en una solución AMI + MDMS. Ninguna de esas
tres oportunidades avanzó a contratación.

Ahora se retoma la misma idea, pero como **producto propio de rensoftlabs** — en la misma
línea que RenFlow, GoNextStep, BillBoss, CreditFlow y Renfy Home — en lugar de como proyecto
de integración a la medida para un cliente puntual. El producto está en fase de **ideación**:
este documento es el primer paso formal para convertirlo en algo construible.

## 2. Problema a resolver

Las empresas de servicios públicos (energía, agua, gas) que despliegan medidores
inteligentes (AMI) enfrentan tres problemas recurrentes, bien conocidos en la industria:

1. **Fragmentación de fuentes**: medidores y concentradores de múltiples marcas y protocolos
   (DLMS/COSEM, ANSI C12.19/C12.22, protocolos propietarios) que no hablan entre sí ni con el
   sistema comercial (CIS) sin una capa de integración dedicada.
2. **Calidad de la medición**: sin un proceso VEE (Validación/Estimación/Edición) sistemático,
   los datos crudos de cientos o miles de lecturas por medidor-mes producen facturación
   incorrecta, reclamos y pérdida de confianza del suscriptor.
3. **Desconexión entre medición y control operativo**: suspender o reconectar el servicio
   (cartera vencida, fraude, orden judicial) sigue dependiendo de visitas de campo si no hay
   un canal de comandos confiable hacia el medidor/concentrador.

## 3. Objetivo del producto

Construir un **MDM (Meter Data Management) completo con Head End System (HES) propio**,
capaz de:

- Capturar mediciones desde **múltiples fuentes, protocolos y marcas** de medidores y/o
  concentradores (agregadores).
- Procesar esas mediciones con un pipeline **VEE** auditable.
- Entregar consumos validados al **sistema comercial** (CIS/facturación) de la ESP —
  propio o de terceros.
- Enviar **comandos de control** al controlador de red del medidor: suspensión, reconexión
  (y, si aplica, corte y reconexión remota completa).
- **Analizar la red más allá del medidor individual**: agregar consumos y pérdidas por zona
  (balance hídrico/energético) y mantener modelos de red (hidráulicos/eléctricos) para
  planificación y análisis operativo — ver §4.
- **Mantener un gemelo digital del inventario operativo de la red** (activos, conectividad,
  atributos), y generar desde ahí las órdenes de mantenimiento de equipos — ejecutadas en
  campo por **BayForce**, sin duplicar esa capacidad dentro de RenfyGrid.

### Principio de modularidad — "à la carte" (agregado 2026-09-10)

RenfyGrid **no se vende obligatoriamente como paquete completo**. Cada capa (§4) es un
servicio independiente que puede operar:
- Con datos capturados por el HES propio de RenfyGrid, **o**
- Con datos que ya vienen de sistemas del cliente (un HES/CIS de terceros, un SIG existente,
  exportes de medición ya procesados) — igual que hace un competidor observado en el mercado
  (Netbase/Crowder, ver nota de origen abajo), que solo ingiere datos vía API sin capturar
  medición él mismo.

Esto habilita dos motions comerciales distintas con el mismo producto:
1. **Paquete completo** (HES+VEE+Consumos+Control) para el ICP original (ESP pequeñas/medianas
   sin AMI/MDM propio, §5).
2. **Módulos sueltos** (p. ej. solo Balance de Red + Modelado de Red) para utilities grandes que
   ya tienen su propia capa de medición/CIS, pero no tienen — o quieren reemplazar — la capa de
   análisis de pérdidas y modelado de red. Esto abre utilities más grandes que el ICP original
   como clientes de un subconjunto de RenfyGrid, sin comprometer el foco SMB del paquete
   completo.

*Nota de origen:* estas dos capacidades (Balance de Red, Modelado de Red) se agregaron al
alcance tras revisar la propuesta de un proveedor especializado (Netbase, de Crowder
Consulting) para un prospecto de agua a gran escala — reveló una capa adyacente de alto valor
que RenfyGrid no cubría. El documento de ese proveedor es material confidencial de un tercero
sobre un cliente puntual — no se referencia con más detalle aquí a propósito; el hallazgo de
producto (la capa en sí, y el principio de modularidad) sí queda incorporado al plan.

## 4. Alcance de la Fase de producto (in/out)

**Dentro de alcance (lo que el usuario pidió explícitamente):**

| Capa | Responsabilidad |
|---|---|
| **HES (Head End System)** | Registro y gestión de medidores/concentradores, conversión multi-protocolo, lectura remota programada y bajo demanda, recepción de eventos/alarmas, envío de comandos (suspensión/corte/reconexión) |
| **Almacenamiento** | Histórico de lecturas crudas (data lake), metadatos de medidor/ubicación, retención y respaldo |
| **VEE** | Validación (rangos, formato, coherencia, integridad) → Estimación (datos faltantes, interpolación/histórico) → Edición (manual auditada, con trazabilidad) |
| **Gestión de Consumos** | Agregación de datos validados en consumo facturable, reglas de crítica/desviación, preparación para facturación, órdenes de relectura/inspección |
| **Control** | Recepción y ejecución de solicitudes de suspensión/corte/reconexión, confirmación de estado hacia el sistema comercial |
| **Balance de Red** *(agregado 2026-09-10)* | Agregación de caudales/consumos por zona/circuito/DMA, cálculo de pérdidas (metodología IWA Top-Down/Bottom-Up para agua; balance equivalente para energía/gas), identificación de Agua/Energía No Facturada |
| **Modelado de Red** *(agregado 2026-09-10)* | Gestión del ciclo de vida de modelos de red (creación, calibración, mantenimiento), integración con motores estándar (EPANET/WNTR para agua), soporte a planificación estratégica |
| **Gemelo Digital** *(agregado 2026-09-10)* | Inventario operativo de la red: activos (tuberías, válvulas, tanques, bombas, medidores), su conectividad/topología y atributos operativos (material, diámetro, capacidad, año, condición) — el insumo real que necesitan Balance de Red y Modelado de Red para simular; sincronizable con el SIG del cliente |
| **Gestión de Mantenimiento** *(agregado 2026-09-10)* | Genera órdenes de mantenimiento (preventivo/correctivo) a partir de la condición del activo, resultados de simulación o anomalías de balance; la ejecución en campo (ruteo, cuadrillas, app móvil, liquidación) se delega a **BayForce** — ya en el portafolio, no se reconstruye |

**Módulos "à la carte":** cualquier subconjunto de las 9 capas de arriba es una oferta válida —
ver el principio de modularidad en §3. No todas dependen entre sí (Balance de Red, Modelado de
Red y Gemelo Digital pueden operar con datos externos, sin HES/VEE propios).

**Fuera de alcance por ahora** (a definir si se agregan en fases posteriores):
- CIS/facturación completo (se asume integración con un CIS existente, propio o del cliente).
- GIS, SCADA, ADMS, OMS como sistemas completos — el producto se integra con ellos, no los reemplaza (Modelado de Red consume/exporta datos de SIG, no reemplaza un SIG).
- App móvil de campo y BI/analítica avanzada — quedan como fase futura, no bloquean el MVP.

## 5. Mercado y usuario objetivo (validado contra benchmark de industria, 2026-09-10)

- **ICP primario**: empresas prestadoras de servicios públicos pequeñas/medianas
  (energía, acueducto, gas) en LatAm que ya invirtieron o van a invertir en medidores
  inteligentes pero no tienen presupuesto ni interés en un MDM de gran escala tipo
  Oracle Utilities / Itron / Landis+Gyr.
- **Punto de partida real**: el interés ya validado en 2024 vino del sector eléctrico
  colombiano — es el segmento más natural para el primer piloto, aunque el diseño debe
  quedar preparado para agua y gas desde el principio (mismo modelo conceptual, distinto
  adaptador de protocolo de medidor).
- **Relación con Renfy Home**: complementario, no competidor — Renfy Home es gestión de
  conjuntos residenciales (control de acceso/porterías); RenfyGrid es medición/facturación de
  servicios públicos. Podrían compartir cliente final (ESP) en municipios pequeños.
- **Sinergia real de portafolio con BayForce**: la Gestión de Mantenimiento de RenfyGrid genera
  las órdenes; BayForce (ya vendido en el portafolio como gestión de fuerza de campo para
  utilities) las ejecuta — mismo patrón de "no reconstruir lo que ya existe" que se aplicó con
  Gurux/WNTR, pero a nivel de producto del portafolio en vez de librería externa. Primer caso
  real de dos productos del portafolio integrándose entre sí, no solo compartiendo cliente.
- **El competidor real no son los gigantes.** El benchmark de industria (`00-benchmark-industria.md`)
  confirma que Itron, Landis+Gyr y Oracle Utilities MDM están sobredimensionados para este ICP.
  El benchmark de producto real es contra plataformas SaaS multi-tenant que **ya operan en el
  mismo segmento**: **Bynry (SMART360)** — el comparable más cercano, 3.000–100.000 conexiones,
  go-live en 12-24 semanas —, **Kalki.io (MDAS)** y **Energyworx**.
- **Diferenciador validado**: cobertura multi-utility (energía+agua+gas) desde el mismo núcleo
  — ninguno de los comparables directos lo resuelve así hoy (Bynry no tiene HES propio; los
  especialistas por utility cubren un solo vertical; Diehl Metering es el más parecido en
  alcance pero vende medidores, no SaaS).
- **Gas como plan B de piloto**: es el vertical con menos competencia SaaS-SMB independiente —
  candidato si el piloto de energía no logra tracción rápida.
- **ICP secundario habilitado por la modularidad**: utilities grandes (fuera del rango
  3.000–100.000 conexiones) que ya tienen medición/CIS propios pero no una capa de Balance de
  Red/Modelado de Red — se les vende ese subconjunto solo, sin competir con su AMI/MDM
  existente. No es el foco primario del piloto, pero queda como vía de entrada a cuentas
  grandes sin diluir el paquete completo para el ICP SMB.

## 6. Restricciones y riesgos identificados

- **Interoperabilidad real**: cada fabricante de medidor implementa DLMS/COSEM o ANSI C12
  con variaciones propias — el HES necesita una capa de adaptadores por protocolo/marca,
  no un parser único.
- **Volumen de datos**: de 1 lectura/medidor-mes a cientos/miles — la capa de almacenamiento
  debe diseñarse para ese salto desde el día 1, aunque el piloto sea pequeño.
- **Ciberseguridad del canal de control**: enviar comandos de suspensión/reconexión a
  infraestructura física exige autenticación fuerte, cifrado y auditoría — es la
  funcionalidad con mayor impacto si falla o se abusa (des/reconexión indebida).
- **Regulación local**: normas de medición y corte de servicio varían por país/regulador
  (CREG en Colombia, etc.) — puede afectar qué acciones de control son automatizables vs.
  requieren aprobación humana.
- **Riesgo comercial ya conocido**: las 3 oportunidades de 2024 no avanzaron — vale la pena
  entender por qué (¿precio, madurez del producto, timing, decisión del comité?) para no
  repetir el mismo obstáculo ahora que se construye como producto propio.
- **Falta de canal de venta definido — riesgo #1, en paridad con los técnicos** (confirmado por
  el benchmark de industria): los comparables directos (Bynry, Kalki.io, Energyworx) ya tienen
  clientes reales; RenfyGrid tiene cero. La brecha técnica se cierra en meses (ver plan de
  sprints); la comercial es la misma que frenó las 3 oportunidades de 2024.

## 7. Abiertos para decidir antes de pasar a Arquitectura

Se proponen valores por defecto razonables para avanzar ya; se corrigen si no encajan:

1. ~~**Nombre comercial**~~ — **resuelto: `RenfyGrid`** (2026-09-10).
2. **Modelo de despliegue** (default propuesto: **SaaS multi-tenant como modelo primario**,
   arquitectado para permitir despliegue dedicado/on-premise si un cliente grande lo exige).
   Encaja mejor con "producto de portafolio" que un proyecto de integración a medida por
   cliente.
3. **Utility objetivo primero** (default propuesto: **energía eléctrica**, por ser el
   segmento donde ya hubo interés real en 2024; **gas queda documentado como plan B** si el
   piloto de energía no logra tracción rápida — ver benchmark de industria).
4. **Qué pasó con las 3 oportunidades de 2024**: si el usuario tiene claridad sobre por qué
   no avanzaron, es información valiosa para no repetir el mismo bloqueo — el benchmark de
   industria eleva esto a riesgo #1, ya no es opcional resolverlo antes del piloto.

## 8. Próximos pasos

Con este planteamiento como base, se pasa a la **Fase 2: Arquitectura general** — stack
tecnológico, modelo de despliegue, y diagrama de componentes del HES + MDM + bus de
integración.
