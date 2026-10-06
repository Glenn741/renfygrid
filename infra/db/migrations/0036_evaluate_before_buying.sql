-- RenfyGrid -- 0036_evaluate_before_buying.sql
-- Track D, D3.2 (2026-10-06): ficha "Evaluar antes de comprar" de la Guia 3
-- de Municipios Azules (seccion 3.6), textos literales:
--   "Antes de comprar una planta o equipos nuevos, la JAAPS debe revisar si
--    la infraestructura existente puede rehabilitarse, adecuarse o
--    repotenciarse."
-- Cada pregunta tiene su propia escala (items[].options, 0026) y lo que la
-- guia dice que orienta va como ayuda del item (items[].help). No genera
-- hallazgos ni puntaje: es una ayuda para decidir, con observacion pedida.

INSERT INTO checklist_template (id, pack_id, kind, title, purpose, scale, items, stage_code) VALUES
('MA-G3-BUY', 'EC-MUNICIPIOS-AZULES', 'self_assessment', 'Evaluar antes de comprar',
 'Antes de comprar una planta o equipos nuevos, la JAAPS debe revisar si la infraestructura existente puede rehabilitarse, adecuarse o repotenciarse. Muchas veces el problema no es que falte todo el sistema, sino que algunas unidades están abandonadas, subdimensionadas, sin mantenimiento o mal operadas.',
 '[]',
 '[{"key": "source_changed", "text": "¿La fuente cambió su calidad o caudal?", "help": "Solicitar análisis y revisar capacidad.",
    "options": [{"code": "yes", "label": "Sí", "finding": false, "ask_note": true, "score": 0},
                {"code": "no", "label": "No", "finding": false, "score": 0},
                {"code": "unknown", "label": "No sabemos", "finding": false, "ask_note": true, "score": 0}]},
   {"key": "population_grew", "text": "¿La población creció desde que se construyó el sistema?", "help": "Evaluar si el sistema quedó subdimensionado.",
    "options": [{"code": "yes", "label": "Sí", "finding": false, "ask_note": true, "score": 0},
                {"code": "no", "label": "No", "finding": false, "score": 0},
                {"code": "unknown", "label": "No sabemos", "finding": false, "ask_note": true, "score": 0}]},
   {"key": "unused_units", "text": "¿Existen filtros, tanques o unidades sin uso?", "help": "Revisar si se pueden recuperar.",
    "options": [{"code": "yes", "label": "Sí", "finding": false, "ask_note": true, "score": 0},
                {"code": "no", "label": "No", "finding": false, "score": 0}]},
   {"key": "operation_or_design", "text": "¿El problema es de operación o de diseño?", "help": "Definir mantenimiento o asistencia técnica.",
    "options": [{"code": "operation", "label": "Operación", "finding": false, "ask_note": true, "score": 0},
                {"code": "design", "label": "Diseño", "finding": false, "ask_note": true, "score": 0},
                {"code": "unknown", "label": "No sabemos", "finding": false, "ask_note": true, "score": 0}]},
   {"key": "supplier_manual", "text": "¿El proveedor entregó manual y capacitó al operador?", "help": "Exigir documentación y capacitación.",
    "options": [{"code": "yes", "label": "Sí", "finding": false, "score": 0},
                {"code": "no", "label": "No", "finding": false, "ask_note": true, "score": 0}]}]',
 'G3');
