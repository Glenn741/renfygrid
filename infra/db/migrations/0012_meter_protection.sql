-- RenfyGrid -- 0012_meter_protection.sql
-- Control (SCR), Sprint C11-5: lista de cuentas protegidas contra
-- suspension/desconexion -- benchmark real (docs/05-ejecucion.md Sprint
-- C11-5): ningun MDM/CIS de referencia ejecuta un corte sin chequear si la
-- cuenta es un "usuario de proteccion especial"; en Colombia esto es
-- requisito real (Ley 142 de 1994 + normas de la CRA/CREG posteriores --
-- Resolucion CREG 108/1997 exige considerar "sujetos de especial
-- proteccion" antes de suspender, con derecho a debido proceso).
--
-- Alcance deliberadamente acotado (confirmado con el usuario): esto es
-- SOLO la bandera de exclusion + quien/cuando/por-que-en-texto-libre la
-- marco -- la clasificacion real del cliente (es un hospital, un colegio,
-- tiene tarifa especial...) es dato de CIS, fuera del alcance de un MDM
-- como RenfyGrid. Marcar la bandera es una decision operativa que ya se
-- tomo (por carga masiva desde una lista externa, o a mano) -- no una
-- reimplementacion del CIS.

ALTER TABLE meter ADD COLUMN protected_from_suspension boolean NOT NULL DEFAULT false;
ALTER TABLE meter ADD COLUMN protection_reason text;
ALTER TABLE meter ADD COLUMN protection_marked_by text;
ALTER TABLE meter ADD COLUMN protection_marked_at timestamptz;
