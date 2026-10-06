# RenfyGrid: estructura funcional sobre estándares mundiales de operación de acueductos

2026-10-06. Pedido del usuario: RenfyGrid es un sistema integral para operar acueductos en
diferentes regiones y países. No debe haber referencias puntuales a entidades (ARCA u otras) en la
estructura del sistema. La guía de ARCA (Municipios Azules) se aplica como base, pero como un
**paquete** sobre una estructura alineada con estándares de clase mundial.

## 1. Referencias de clase mundial

| Referencia | Quién | Qué aporta a la estructura |
|---|---|---|
| **Water Safety Plan Manual, 2.ª ed. (2023)** | OMS + IWA | La columna vertebral. Riesgo y control "de la captación al consumidor" en 11 módulos: describir el sistema por etapa (fuente y cuenca, tratamiento, almacenamiento y distribución), identificar peligros, medidas de control, monitoreo operativo, acciones correctivas, verificación, mejora y revisión. La 2.ª edición agrega clima, equidad y resiliencia. |
| **Guías para la calidad del agua de consumo (GDWQ)** | OMS | Marco de calidad: objetivos basados en salud, WSP y vigilancia independiente. Los valores numéricos de cada país son **datos** (paquete regulatorio). |
| **Sanitation Safety Planning, 2.ª ed. (2022)** | OMS | El equivalente del WSP para el saneamiento. Riesgo a lo largo de la cadena: baño, contención y tratamiento, transporte, tratamiento y uso o disposición final. |
| **ISO 24510 / 24511 / 24512 (rev. 2024)** | ISO TC 224 | Servicio a los usuarios (24510), gestión del prestador de saneamiento (24511) y gestión del prestador de agua potable (24512), con evaluación del servicio. |
| **ISO 24516-1…4 sobre ISO 55000** | ISO | Gestión de activos aplicada al agua: redes de distribución (1), plantas, bombeos, tanques y dosificación (2), alcantarillado (3) y plantas de aguas residuales (4). |
| **AWWA G100-17 y G200-21** | AWWA | Requisitos de operación y gestión de plantas de tratamiento (G100) y de redes de distribución (G200): calidad, programas de gestión, operación y mantenimiento, verificación. |
| **Indicadores de desempeño IWA, 3.ª ed.** | IWA | El sistema de indicadores de referencia mundial, aplicable a cualquier tamaño de prestador y con cobertura de países en desarrollo. Incluye el **balance hídrico** (agua no contabilizada), que RenfyGrid ya usa en Balance de Red. |
| **IBNET** | Banco Mundial | Indicadores y definiciones estándar para comparar prestadores (cobertura, agua no contabilizada, eficiencia de cobro, cobertura de costos de operación), con datos de más de 5.000 prestadores de más de 150 países. |
| **AquaRating** | BID + IWA | Calificación de prestadores (más usada en América Latina): 8 áreas y 112 elementos. Las áreas son calidad del servicio, inversiones, eficiencia operativa, gestión empresarial, sostenibilidad financiera, acceso, gobierno corporativo y sostenibilidad ambiental. |
| **Effective Utility Management (EUM) y CUPSS** | EPA (EE. UU.) | Los 10 atributos de un prestador bien gestionado (versión 2024). CUPSS es la referencia de gestión de activos para **sistemas pequeños**: inventario, órdenes de trabajo, proyección financiera y plan de activos. |
| **Escalera de servicios JMP (ODS 6.1 y 6.2)** | OMS/UNICEF | Nivel de servicio por conexión. **Gestionado de forma segura** = en la vivienda, disponible cuando se necesita y libre de contaminación. **Básico** = recolección de 30 minutos o menos. **Limitado** = más de 30 minutos. |

## 2. Estructura funcional

La estructura sigue la cadena del WSP (agua) y la del SSP (saneamiento). Los dominios de gestión
salen de ISO 24512, AWWA G100/G200 e ISO 24516. Cada dominio dice qué módulo de RenfyGrid lo
cubre hoy y qué le falta.

| Dominio | Estándar que lo define | En RenfyGrid hoy | Brecha frente al estándar |
|---|---|---|---|
| **1. Sistema y activos.** Componentes por etapa (captación, tratamiento, almacenamiento, distribución, saneamiento), mapa e inventario | WSP módulo 2, ISO 24516, CUPSS | Gemelo digital, tipos de componente por etapa, recorrido, tren de tratamiento | Criticidad y condición del activo, vida útil y costo de reposición (ISO 24516/55000) |
| **2. Riesgo y seguridad del agua.** Peligros, medidas de control, límites, acciones correctivas | WSP módulos 3–6 | Hallazgos, listas de verificación con acción y semáforo | **Registro de peligros por etapa** con su medida de control, límite operativo y acción correctiva (la matriz del WSP). Hoy los hallazgos son sueltos. |
| **3. Operación del tratamiento.** Monitoreo operativo, dosificación, bitácora | AWWA G100, WSP módulo 6 | Operación diaria (D1): mediciones, bitácora, dosificación, app sin conexión | — |
| **4. Distribución.** Presión, continuidad, calidad en red, pérdidas | AWWA G200, IWA (balance hídrico) | Puntos de muestreo en red, Balance de Red, MDM y VEE, modelado hidráulico | **Continuidad del servicio** (horas por día por sector) e **interrupciones** registradas; presión en puntos críticos |
| **5. Calidad y verificación.** Plan de muestreo, laboratorio, cumplimiento | GDWQ, WSP módulo 7 | Calidad del agua (D2) | — (los valores de referencia de cada país son paquete) |
| **6. Mantenimiento.** Preventivo, correctivo, emergente, calendario | ISO 24516, CUPSS | CMMS (D3) | Ligar costo de mantenimiento a activo y criticidad |
| **7. Insumos y seguridad del personal** | AWWA G100 (operación), buenas prácticas | Bodega y EPP (D4) | — |
| **8. Emergencias y resiliencia** | WSP 2.ª ed. (clima, resiliencia) | Emergencias (D5) | Escenarios climáticos (sequía, inundación) como amenazas del registro de peligros |
| **9. Saneamiento** | SSP, ISO 24511 | Saneamiento (D6) | Riesgo por etapa de la cadena del SSP (mismo patrón que el dominio 2) |
| **10. Usuarios y servicio** | ISO 24510, JMP | No construido (era D8, padrón) | **Padrón por conexión con nivel de servicio JMP**, reclamos y atención al usuario (ISO 24510) |
| **11. Comercial y financiero** | IBNET, AquaRating (sostenibilidad financiera), ISO 24512 | No construido (D8–D11) | Facturación y recaudo, caja, costos, tarifa, presupuesto |
| **12. Gobierno y mejora continua** | WSP módulos 8–11, EUM, AquaRating (gobierno) | Plan mínimo y de mejora (D7), ruta de capacitación | — |
| **13. Indicadores y comparación** | IWA, IBNET, AquaRating, JMP | Tablero de agrupación (D12) con indicadores propios | Calcular **indicadores con definición estándar** (IWA/IBNET) como catálogo: agua no contabilizada, continuidad, eficiencia de cobro, cobertura de costos |
| **14. Reportes a autoridades** | Cada país | Informe de cumplimiento (D12.3) | — (el formato de cada autoridad es paquete) |

## 3. Capas: qué es estructura y qué es paquete

1. **Núcleo (estructura).** Los 14 dominios, la cadena de etapas y los motores (reglas,
   listas, hallazgos, detectores, indicadores). No nombra países, entidades ni programas.
2. **Paquete regulatorio por país** (hoy `EC-ARCA`). Valores de referencia con su norma, tipos de
   punto de muestreo, formato del informe a la autoridad e instituciones de emergencia.
3. **Paquete de programa** (hoy `EC-MUNICIPIOS-AZULES`). Guías, listas, rutas de capacitación,
   ejemplos, plan mínimo y fichas.
4. **Terminología por paquete u organización.** Cómo se llama el prestador (junta, JAAP, ASADA,
   comité de agua, empresa de servicios públicos), su directiva, la autoridad y el gobierno local.
   Hoy "junta" está escrito en la interfaz y en los mensajes del backend unas 75 veces.
5. **Configuración de la organización.** Moneda, región (formato de números y fechas), zona
   horaria (ya existe) y umbrales.

## 4. Lo que hay que corregir en el código actual

**Valores fijos** (auditoría del 2026-10-06):
- moneda "USD" en 5 lugares;
- formato regional "es" en 17 lugares;
- plantilla `MA-G3-7H` en la página Plan de Mejora;
- nombres de formatos de la guía (7C, 7E, 7F, 7H, 7G.2, Guía 6) en textos de la interfaz y en una
  sugerencia del backend;
- 6 mapas de etiquetas de estados y prioridades en el frontend;
- frases armadas en el backend.

**Referencias a entidades** en la interfaz:
- ARCA, GAD, MSP, ECU 911 y COE cantonal (Emergencias, Calidad, Informe);
- JAAPS (Bodega, Observaciones);
- "Taller Municipios Azules" (seguimiento).

En el backend solo aparecen en comentarios de trazabilidad, que se mantienen porque citan la
fuente.

**Término "junta":** pasa al catálogo de terminología. Los mensajes del backend dicen
"organización".

## 5. Consecuencias para lo que sigue

- **D8 se rehace como dominio 10, "Usuarios y servicio"** (ISO 24510 + JMP):
  - padrón por conexión, ligado al gemelo digital y a los medidores;
  - estado de la conexión y nivel de servicio JMP;
  - reclamos y atención;
  - lo que pide la Guía 4 queda cubierto como paquete encima.
- **D9–D11 pasan a ser el dominio 11, "Comercial y financiero":** caja, facturación, costos, tarifa
  y presupuesto, con la moneda de la organización y los indicadores IBNET de eficiencia de cobro y
  cobertura de costos.
- **Brechas nuevas que salen del estándar y no de la guía:**
  - registro de peligros del WSP (dominio 2);
  - continuidad del servicio e interrupciones (dominio 4);
  - indicadores IWA/IBNET como catálogo (dominio 13).
