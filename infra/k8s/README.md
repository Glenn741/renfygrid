# RenfyGrid en k3s

Decisión tomada 2026-09-10 (ver `docs/02-arquitectura-general.md` principio 4, y la
comparación de pros/contras en `docs/05-ejecucion.md`): los servicios de aplicación de
RenfyGrid se despliegan en **k3s** (Kubernetes liviano, un solo binario) desde el Sprint 0 —
no Docker Compose + systemd, y no un clúster gestionado (EKS/GKE/AKS) tampoco.

**✅ EJECUTADO Y VERIFICADO (2026-09-10)** — ver la bitácora en `docs/05-ejecucion.md` (F46).
El clúster corre en **WSL2 Ubuntu de este PC** (nodo `gmolthpad`, k3s `v1.36.4+k3s1`, Docker
`29.1.3` ya estaba instalado ahí por el flujo de build de renvox). Se accede desde Windows con:

```bash
wsl -d Ubuntu bash -c "sudo k3s kubectl get pods -n renfygrid"
```

`update.k3s.io` devolvía un certificado TLS incorrecto (de Traefik, no del dominio real) al
instalar — se resolvió fijando la versión exacta (`INSTALL_K3S_VERSION`) para que el
instalador no dependa de ese endpoint. Migrar a un servidor Linux dedicado más adelante es
solo repetir el mismo `curl -sfL https://get.k3s.io | sh -`, no un cambio de manifiestos.

## Qué corre dentro del clúster y qué no

- **Dentro de k3s** (stateless, un Deployment + Service por servicio): adaptadores HES, motor
  VEE, Gestión de Consumos, módulo SCR, Balance de Red, Modelado de Red, Gemelo Digital,
  Gestión de Mantenimiento, Portal/API.
- **Fuera de k3s** (con estado, vía `docker-compose.yml` en la raíz del repo): PostgreSQL +
  TimescaleDB, Redis. Los pods se conectan a estos por host/IP del servidor, no por Service de
  Kubernetes.

## Por qué un solo namespace, no uno por tenant

La multi-tenencia de RenfyGrid vive en la base de datos (Row-Level Security, ver
`docs/03-diseno.md` §1) — **no** en el aislamiento de Kubernetes. Un solo namespace
`renfygrid` aloja un Deployment por *servicio* (no por tenant); todos los tenants comparten
los mismos pods, aislados por `tenant_id` + RLS. Esto evita explotar el número de namespaces/
Deployments a medida que crecen los tenants — que es justo el tipo de complejidad operativa
que se buscó evitar al no ir directo a un clúster gestionado grande.

## Bootstrap de k3s (ya corrido en WSL2 de este PC — comandos para replicar en otro servidor)

```bash
# En el servidor destino (Linux):
curl -sfL https://get.k3s.io -o /tmp/k3s-install.sh
sudo INSTALL_K3S_VERSION='v1.36.4+k3s1' sh /tmp/k3s-install.sh   # version fijada, ver nota arriba

# Verificar
sudo k3s kubectl get nodes

# Namespace del proyecto
sudo k3s kubectl apply -f base/namespace.yaml
```

## Cómo construir y desplegar un servicio nuevo (patrón usado por dummy-config-reader)

```bash
# 1. Build (WSL, donde vive Docker)
docker build -t renfygrid/<servicio>:<tag> services/<servicio>/

# 2. Importar al containerd de k3s (no hay registry todavía)
docker save renfygrid/<servicio>:<tag> | sudo k3s ctr images import -

# 3. Aplicar el manifiesto (imagePullPolicy: Never — la imagen ya está local)
sudo k3s kubectl apply -f infra/k8s/services/<servicio>/deployment.yaml
```

## Estructura prevista (a medida que existan servicios reales que desplegar)

```
infra/k8s/
  README.md              (este archivo)
  base/
    namespace.yaml
  services/
    hes-adapter-dlms/
      deployment.yaml
      service.yaml
    vee-engine/
      deployment.yaml
      service.yaml
    ...(un directorio por servicio, mismo patrón)
  ingress.yaml             (expone portal-api vía nginx, mismo patrón TLS que rnsftlbs)
```

Deliberadamente **no se escriben manifiestos de servicios que todavía no existen como código**
(Sprint 1 en adelante) — hacerlo ahora sería scaffolding vacío. El primer manifiesto real
(`services/dummy-config-reader/`, ver `docs/05-ejecucion.md` F46) es un servicio dummy de
prueba del Sprint 0, ya construido, importado y corriendo (`Running`) — confirma que el
patrón de despliegue (build → import → apply, initContainer Loader + contenedor que solo
lee snapshot) funciona antes de construir servicios reales sobre él.
