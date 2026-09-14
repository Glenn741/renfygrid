-- RenfyGrid -- 0018_network_balance_derived_flag.sql
-- Track B, Sprint B2 (completo en esta ronda) -- ahora `real_losses`
-- puede quedar CALCULADO por RenfyGrid (metodo Top-Down, residual del
-- balance) en vez de siempre venir como dato directo del llamador. Se
-- guarda de donde salio -- proveniencia real, nunca implicita.

ALTER TABLE network_balance ADD COLUMN real_losses_derived boolean NOT NULL DEFAULT false;
