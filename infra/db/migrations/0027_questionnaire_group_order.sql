-- RenfyGrid -- 0027_questionnaire_group_order.sql
-- Correccion de 0026 (2026-10-05): en `analysis.group_by[].values` los grupos
-- iban como objeto {code: label}. Un objeto jsonb no conserva el orden de sus
-- claves (Postgres las ordena por largo), y el analisis de la CAP mostraba
-- las dimensiones como Actitudes, Practicas, Conocimientos en vez del orden
-- de la Guia 7 (T-05). Ahora `values` es una lista [{code, label}] en el
-- orden de la guia.
UPDATE checklist_template
SET analysis = jsonb_set(
    jsonb_set(analysis, '{group_by,0,values}',
        '[{"code": "G1", "label": "Guía 1"}, {"code": "G2", "label": "Guía 2"}, {"code": "G3", "label": "Guía 3"},
          {"code": "G4", "label": "Guía 4"}, {"code": "G5", "label": "Guía 5"}, {"code": "G6", "label": "Guía 6"}]'),
    '{group_by,1,values}',
    '[{"code": "knowledge", "label": "Conocimientos"}, {"code": "attitude", "label": "Actitudes"},
      {"code": "practice", "label": "Prácticas"}]')
WHERE id = 'MA-CAP'
  AND analysis->'group_by'->0->>'key' = 'guide'
  AND analysis->'group_by'->1->>'key' = 'dimension';
