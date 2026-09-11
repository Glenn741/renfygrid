#!/bin/bash
# Sprint C11 -- aplica las migraciones 0010 (poller_retry_queue, F08) y 0011
# (particionado de raw_reading, F10) en produccion (essmarplapp02), con
# respaldo real primero (pg_dump). Pendiente de correr: quedo bloqueado por
# el clasificador de auto-modo ("Production Deploy") -- ver docs/05-ejecucion.md,
# Sprint C11, seccion "Pendiente real".
#
# Uso (desde este PC, sube las migraciones y este script, luego lo corre):
#   pscp -pw "opc" -P 34 infra/db/migrations/0010_poller_retry_queue.sql opc@158.101.17.14:/tmp/
#   pscp -pw "opc" -P 34 infra/db/migrations/0011_raw_reading_partitioning.sql opc@158.101.17.14:/tmp/
#   pscp -pw "opc" -P 34 infra/db/deploy_0010_0011_to_production.sh opc@158.101.17.14:/tmp/
#   plink -pw "opc" -P 34 opc@158.101.17.14 "bash /tmp/deploy_0010_0011_to_production.sh"
#
# Despues de esto: desplegar poller.py (fuente) y vee_engine.py (compilar con
# Nuitka) + run_vee_pass.py/run_vee_estimation.py (fuente) +
# services/common/renmeter_common/partition_maintenance.py (fuente, es un job
# aparte igual que refresh_obis_mapping_cache.py) a essmarplapp02, y
# reiniciar los servicios que correspondan.
set -e
BACKUP=/tmp/renfygrid_pre_c11_backup_$(date +%Y%m%d_%H%M%S).dump
sudo -u postgres pg_dump -Fc -d renfygrid -f "$BACKUP"
echo "Backup: $BACKUP ($(sudo -u postgres stat -c%s "$BACKUP" 2>/dev/null || stat -c%s "$BACKUP") bytes)"
sudo -u postgres psql -d renfygrid -f /tmp/0010_poller_retry_queue.sql
sudo -u postgres psql -d renfygrid -f /tmp/0011_raw_reading_partitioning.sql
echo "--- verificacion post-migracion ---"
sudo -u postgres psql -d renfygrid -c "\d raw_reading" | head -25
sudo -u postgres psql -d renfygrid -c "SELECT relname FROM pg_class WHERE relname LIKE 'raw_reading%' ORDER BY relname;"
sudo -u postgres psql -d renfygrid -c "SELECT relname FROM pg_class WHERE relname = 'poller_retry_queue';"
