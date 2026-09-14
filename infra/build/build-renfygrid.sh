#!/bin/bash
set -euo pipefail

REPO="/mnt/c/PCGM/RENSOFTLABS/core/renmeter/services"
NUITKA="$HOME/nuitka-env-renfygrid/bin/nuitka"
DIST="/home/gmol/renfygrid-dist"

declare -A SKIP=(
  # __init__.py de renmeter_common: Nuitka rechaza compilar un __init__.py
  # de paquete de forma standalone ("to compile a package, specify its
  # directory but, not the '__init__.py'") -- limitacion real de la
  # herramienta, no una decision de politica. Encontrado 2026-09-14: este
  # build llevaba desde el Sprint C11 fallando en silencio en cada corrida
  # (el script no fallaba duro por un archivo individual) y produccion
  # tenia el .py fuente desde el primer despliegue manual, nunca
  # recompilado -- 109 bytes, un simple re-export sin logica de negocio
  # (`from .config_cache import ...`). Formalizado aca en vez de dejarlo
  # como un FALLO silencioso.
  [common]='__init__.py dummy_config_loader.py dummy_config_reader.py run_partition_maintenance.py'
  [hes-adapter-dlms]='main.py poller.py seed_demo_data.py refresh_obis_mapping_cache.py event_listener.py'
  [vee-engine]='run_vee_estimation.py run_vee_pass.py refresh_vee_rules_cache.py'
  [consumption]='run_consumption_pass.py'
  [control]=''
  [portal-api]='main.py'
  [network-balance]=''
  [network-model]='seed_demo_networks.py'
  [digital-twin]='seed_demo_assets.py'
  [maintenance]=''
)

declare -A SRC_SUBDIR=(
  [common]='renmeter_common'
)

# Incremental de verdad: si el .so ya existe y es mas nuevo que el .py
# fuente, no se vuelve a compilar (antes se recompilaba TODO el
# portafolio en cada corrida, apoyandose solo en ccache a nivel de
# compilador C -- sigue gastando tiempo real en cada archivo sin cambios;
# esto se salta el archivo por completo). Un archivo "fuente" (SKIP) se
# copia solo si cambio o no existe en destino, mismo criterio.

for svc in common hes-adapter-dlms vee-engine consumption control portal-api network-balance network-model digital-twin maintenance; do
  subdir="${SRC_SUBDIR[$svc]:-}"
  src="$REPO/$svc"
  [[ -n "$subdir" ]] && src="$src/$subdir"
  dist="$DIST/$svc"
  mkdir -p "$dist"
  echo ""
  echo "== $svc ($src) =="
  ok=0; fail=0; skip=0; kept=0; uptodate=0
  for py in "$src"/*.py; do
    [[ -f "$py" ]] || continue
    name=$(basename "$py")
    stem="${name%.py}"

    if echo "${SKIP[$svc]}" | grep -qw "$name"; then
      dest="$dist/$name"
      if [[ -f "$dest" ]] && [[ "$dest" -nt "$py" ]]; then
        uptodate=$((uptodate+1))
        continue
      fi
      cp "$py" "$dist/"
      kept=$((kept+1))
      continue
    fi

    so_file=$(ls "$dist/${stem}".cpython-*.so 2>/dev/null | head -1 || true)
    if [[ -n "$so_file" ]] && [[ "$so_file" -nt "$py" ]]; then
      uptodate=$((uptodate+1))
      continue
    fi

    echo -n "  $name... "
    if "$NUITKA" --module --nofollow-imports "$py" --output-dir="$dist" --remove-output 2>&1 | grep -q 'Successfully created'; then
      echo OK
      ok=$((ok+1))
    else
      echo FALLO
      fail=$((fail+1))
    fi
  done
  echo "  -> $ok compilados, $kept fuente copiada, $uptodate ya al dia (sin tocar), $fail fallidos"
done
