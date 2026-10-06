-- RenfyGrid -- 0041_evidence_stage.sql
-- Track D, D7 (2026-10-06): etapa de la ruta a la que pertenece cada origen
-- de evidencia, para que la ficha 7G.2 de una guia proponga por defecto la
-- evidencia de esa guia (visto en vivo: la 7G.2 de la Guia 3 proponia los
-- "Falta" de la asamblea de la Guia 2). Las listas usan la etapa de su
-- plantilla; un hallazgo manual no tiene etapa y se muestra siempre.

ALTER TABLE evidence_label ADD COLUMN stage_code text;
ALTER TABLE evidence_label ADD CONSTRAINT evidence_label_stage_fkey
    FOREIGN KEY (pack_id, stage_code) REFERENCES process_stage(pack_id, code);

UPDATE evidence_label SET stage_code = 'G3'
WHERE pack_id = 'EC-MUNICIPIOS-AZULES' AND source_kind IN ('reading', 'lab', 'critical_point', 'sludge', 'discharge');
