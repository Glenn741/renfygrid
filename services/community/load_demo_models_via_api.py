"""Registra y simula los modelos hidraulicos de la demo de Gualaceo POR LA
API (como lo haria un usuario): el almacenamiento de modelos `.inp` es del
servicio, no de un script con acceso a BD. Solo libreria estandar.

1. Registra `network-model/demo/gualaceo_rural_sectores.inp` (red rural
   completa, dibujada a mano) y la simula.
2. Para cada zona del tenant que tenga gemelo con fuente, genera el modelo
   desde el Gemelo Digital (`/network-zones/{id}/generate-model`) y lo simula.

Uso:
    python load_demo_models_via_api.py <API base, p.ej. https://renfygrid.rensoftlabs.com/api> <organizacion> <usuario> <clave>
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

INP = Path(__file__).resolve().parents[1] / "network-model" / "demo" / "gualaceo_rural_sectores.inp"
MODEL_NAME = "Red rural Gualaceo — sectores alto y bajo (ilustrativo)"


def call(base: str, method: str, path: str, token: str | None = None, body: dict | None = None) -> dict:
    req = urllib.request.Request(base + path, method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json",
                                          **({"Authorization": f"Bearer {token}"} if token else {})})
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"{method} {path} -> {exc.code}: {exc.read().decode(errors='replace')}") from exc


def main(base: str, org: str, user: str, password: str) -> None:
    token = call(base, "POST", "/auth/login", body={"tenant_id": org, "email": user, "password": password})["access_token"]

    model = call(base, "POST", "/network-models", token, {"name": MODEL_NAME, "inp_content": INP.read_text(encoding="utf-8")})
    sim = call(base, "POST", f"/network-models/{model['model_id']}/simulate", token, {"scenario": "base"})
    print(f"Modelo de la red rural: {model['model_id']} -> simulación {sim.get('simulation_id', '')} OK")

    for zone in call(base, "GET", "/network-zones", token):
        try:
            gen = call(base, "POST", f"/network-zones/{zone['zone_id']}/generate-model", token,
                       {"name": f"Gemelo — {zone['name']}"})
        except RuntimeError as exc:
            print(f"Zona {zone['name']}: sin modelo desde el gemelo ({exc})")
            continue
        sim = call(base, "POST", f"/network-models/{gen['model_id']}/simulate", token, {"scenario": "base"})
        print(f"Zona {zone['name']}: modelo {gen['model_id']} generado desde el gemelo y simulado")


if __name__ == "__main__":
    if len(sys.argv) != 5:
        print(__doc__)
        sys.exit(2)
    main(*sys.argv[1:])
