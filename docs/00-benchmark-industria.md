# Benchmark de industria — RenfyGrid frente al mercado AMI/MDM

**Fecha:** 2026-09-10 · Complementa el Planteamiento (Fase 1). Versión interactiva completa
(mapa de posicionamiento, tablas por vertical, matriz de capacidades) publicada en:
**https://claude.ai/code/artifact/4df65fcd-b599-4fa5-8afb-40d62038d152**

---

## Nota metodológica

Gartner **no publica hoy** un Magic Quadrant de Meter Data Management — el último específico
de la industria de medición es de 2015 y fue descontinuado. Lo que aparece en 2026 al buscar
"Gartner MQ MDM" es el Magic Quadrant de **Master Data Management**, una categoría de TI
distinta (datos maestros empresariales, no medición de servicios públicos). El analista que sí
sigue el mercado de medición es **Guidehouse Insights** (Leaderboard de Smart Meter Analytics,
última edición pública con Oracle/Landis+Gyr/Itron como líderes). El mapa de posicionamiento de
este benchmark es una **lectura propia de Rensoft Labs**, no una calificación de ningún
analista.

## Hallazgo principal: RenfyGrid no compite contra los gigantes

Itron, Landis+Gyr y Oracle Utilities MDM dominan el extremo enterprise — sobredimensionados y
lentos de implementar para el ICP definido en el planteamiento (3.000–100.000 conexiones). El
benchmark real es contra un puñado de plataformas SaaS multi-tenant que **ya operan en el mismo
segmento**:

| Competidor directo | Qué hace | Por qué importa |
|---|---|---|
| **Bynry (SMART360)** | SaaS multi-tenant: billing+medición+CIS+campo, agua/electricidad/gas, 3.000–100.000 conexiones, precio por medidor, go-live en 12-24 semanas | **El más cercano al ICP de RenfyGrid — ya validado en mercado**, con métrica dura de tiempo de implementación |
| **Kalki.io (MDAS)** | HES DLMS/COSEM como SaaS o on-premise | Comparable directo de la capa HES específicamente |
| **Energyworx** | MDM/analítica multi-tenant, arquitectura serverless | Comparable directo de la capa VEE/almacenamiento |

## Diferenciador real de RenfyGrid (en el papel)

**Multi-utility desde el mismo núcleo (energía+agua+gas).** Ninguno de los comparables directos
lo tiene resuelto así: Bynry no tiene protocolo HES propio (depende de integraciones), los
especialistas por utility (Sensus, Aclara, Badger, Neptune) cubren un solo vertical. El más
parecido en alcance es **Diehl Metering**, pero fabrica medidores — no vende SaaS.

## Gas: el hueco competitivo más claro

En electricidad y agua ya existen SaaS-SMB independientes (Bynry, Kalki.io, Energyworx). En
**gas natural** el mercado sigue casi completamente dominado por las mismas marcas grandes
(Itron ~34%, Landis+Gyr ~32%, Aclara ~22%, resto Honeywell/Sensus) — no hay un jugador
SaaS-SMB independiente equivalente. Si el piloto de energía (definido en el Planteamiento §5)
no logra tracción rápida, **gas es la alternativa con menos ruido competitivo directo**.

## Brechas honestas

- **Cero clientes, cero código** frente a comparables que ya tienen tracción real.
- **"Go-live en semanas" es una meta, no un hecho** — Bynry ya lo demuestra con datos (12-24 semanas).
- **Un solo adaptador de protocolo planeado** (DLMS/COSEM) vs. decenas ya soportadas por los líderes.
- **Sin canal de venta definido** — la misma causa que probablemente frenó las 3 oportunidades
  comerciales de 2024 (ver Planteamiento §6), y que sigue sin diagnosticarse.

## Recomendaciones que quedan incorporadas al plan

1. Medir el Sprint 0 en adelante contra el benchmark real de Bynry (12-24 semanas a go-live), no contra un ideal abstracto.
2. Sostener el diseño multi-utility (E+A+G) desde el núcleo como la apuesta diferencial — es la única celda de la matriz de capacidades donde RenfyGrid puede quedar solo si el diseño se mantiene disciplinado.
3. Mantener gas como plan B de priorización de piloto si energía no logra tracción — no como ocurrencia tardía.
4. Tratar la falta de canal comercial como el riesgo #1 del proyecto, en paridad con los riesgos técnicos ya listados en el Planteamiento §6.
