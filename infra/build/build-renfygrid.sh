#!/bin/bash
set -euo pipefail

# Compila todos los servicios de RenfyGrid con Nuitka -- politica de
# portafolio "no fuentes .py en servidores" (ver memoria
# feedback_no_source_on_server_nuitka). Corre en WSL2 (venv Python 3.9
# dedicado, ~/nuitka-env-renfygrid) contra el repo montado en /mnt/c --
# nunca en el servidor de produccion.
#
# Pendiente historico corregido en esta version: el script vivia SOLO en
# WSL (~/build-renfygrid.sh), sin versionar -- si la maquina de build se
# perdia, se perdia tambien el conocimiento de que servicios/SKIP entraban
# al build. Ahora vive en el repo; copiar a ~/build-renfygrid.sh (o
# correrlo desde aca directo) en cualquier maquina de build nueva.
#
# Incremental de verdad (2026-09-13, a pedido del usuario -- "aseurate de
# no estar compilando cada vez"): si el .so ya existe y es mas nuevo que
# el .py fuente, NO se recompila -- antes se recompilaba TODO el
# portafolio en cada corrida, apoyandose solo en ccache a nivel de
# compilador C (que ahorra CPU pero sigue gastando tiempo real de
# invocacion de Nuitka por archivo). Esto salta el archivo por completo
# cuando no cambio.

REPO="/mnt/c/PCGM/RENSOFTLABS/core/renmeter/services"
NUITKA="$HOME/nuitka-env-renfygrid/bin/nuitka"
DIST="/home/gmol/renfygrid-dist"

declare -A SKIP=(
  [common]='dummy_config_loader.py dummy_config_reader.py run_partition_maintenance.py'
  [hes-adapter-dlms]='main.py poller.py seed_demo_data.py refresh_obis_mapping_cache.py event_listener.py'
  [vee-engine]='run_vee_estimation.py run_vee_pass.py refresh_vee_rules_cache.py'
  [consumption]='run_consumption_pass.py'
  [control]=''
  [portal-api]='main.py'
  [network-balance]=''
  [network-model]='seed_demo_networks.py'
  [digital-twin]='seed_demo_assets.py'
)

declare -A SRC_SUBDIR=(
  [common]='renmeter_common'
)

for svc in common hes-adapter-dlms vee-engine consumption control portal-api network-balance network-model digital-twin; do
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
