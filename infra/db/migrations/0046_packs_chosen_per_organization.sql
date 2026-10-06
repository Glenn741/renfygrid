-- RenfyGrid -- 0046_packs_chosen_per_organization.sql
-- 2026-10-06. RenfyGrid opera acueductos en distintos paises
-- (docs/08-estandares-mundiales.md): el paquete normativo de un pais y el de
-- un programa ya no se adoptan por defecto. Una organizacion nueva nace solo
-- con el nucleo y elige su pais y su programa al crearse (o despues, en
-- Configuracion -> Paquetes).
--
-- Antes (0025) todo tenant adoptaba los paquetes de Ecuador para que las
-- organizaciones no se vieran distintas "salvo por sus datos". Esa paridad se
-- mantiene en lo funcional: el nucleo y los motores son los mismos para todas;
-- lo que cambia es el contenido de cada pais o programa, que es dato.
--
-- No se tocan las adopciones existentes: cada organizacion conserva las que
-- tiene y puede desactivarlas.

UPDATE pack SET is_default = false WHERE id IN ('EC-ARCA', 'EC-MUNICIPIOS-AZULES');
