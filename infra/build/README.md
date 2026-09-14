# Build de RenfyGrid (Nuitka)

Compila todos los servicios de `services/` a `.so` con Nuitka -- política de
portafolio "no fuentes `.py` en servidores" (ver memoria
`feedback_no_source_on_server_nuitka`).

## Requisitos (una sola vez, en WSL2)

```bash
wsl --install -d Ubuntu   # si no existe ya un WSL2 Ubuntu
python3.9 -m venv ~/nuitka-env-renfygrid
source ~/nuitka-env-renfygrid/bin/activate
pip install nuitka psycopg[binary] fastapi wntr==1.2.0   # wntr==1.2.0: ultima con wheel cp39, ver network-model/requirements.txt
```

## Uso

```bash
cp infra/build/build-renfygrid.sh ~/build-renfygrid.sh   # o correrlo directo desde el repo
bash ~/build-renfygrid.sh
```

Compila incrementalmente: un archivo cuyo `.so` ya es más nuevo que su
`.py` fuente se salta (no se recompila desde cero cada vez). Salida en
`~/renfygrid-dist/<servicio>/`.

## Desplegar lo compilado

Copiar el `.so`/`.pyi` de cada servicio cambiado a
`essmarplapp02:/opt/renfygrid/<servicio>/` (root:root) y reiniciar
`renfygrid-portal-api`. Ver `docs/05-ejecucion.md` para el detalle de cada
sprint desplegado hasta ahora.
