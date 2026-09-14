"""Configuracion del Portal/API por variable de entorno -- nunca un DSN o
secreto fijo en codigo (mismo principio de 0002_app_role.sql: la contraseña
real se inyecta por entorno/secreto de k8s, nunca queda en un archivo
versionado).
"""

from __future__ import annotations

import os
from dataclasses import dataclass


class MissingConfigError(RuntimeError):
    """Falta una variable de entorno obligatoria -- el servicio no arranca
    con un secreto o DSN adivinado."""


@dataclass(frozen=True)
class Settings:
    dsn: str
    jwt_secret: str
    order_signing_secret: str
    cors_origins: list[str]
    network_model_storage_dir: str
    bayforce_webhook_url: str | None

    @classmethod
    def from_env(cls) -> "Settings":
        missing = [
            name
            for name in ("RENFYGRID_DSN", "RENFYGRID_JWT_SECRET", "RENFYGRID_ORDER_SIGNING_SECRET")
            if not os.environ.get(name)
        ]
        if missing:
            raise MissingConfigError(f"Faltan variables de entorno obligatorias: {missing}")
        # RENFYGRID_CORS_ORIGINS: lista separada por comas -- el Portal Web
        # (Sprint C1) corre en un origen HTTP distinto al API. Default de
        # desarrollo (Vite en :5173), nunca asumido en un entorno real.
        cors_origins = [
            origin.strip()
            for origin in os.environ.get("RENFYGRID_CORS_ORIGINS", "http://localhost:5173").split(",")
            if origin.strip()
        ]
        return cls(
            dsn=os.environ["RENFYGRID_DSN"],
            jwt_secret=os.environ["RENFYGRID_JWT_SECRET"],
            order_signing_secret=os.environ["RENFYGRID_ORDER_SIGNING_SECRET"],
            cors_origins=cors_origins,
            # RENFYGRID_NETWORK_MODEL_STORAGE_DIR (Track B, Sprint B3): donde
            # se guardan los `.inp` subidos -- no es un secreto, pero nunca
            # una ruta fija en codigo; el default solo aplica a desarrollo
            # local, produccion siempre lo fija explicito (systemd Environment=).
            network_model_storage_dir=os.environ.get("RENFYGRID_NETWORK_MODEL_STORAGE_DIR", "./network_model_storage"),
            # RENFYGRID_BAYFORCE_WEBHOOK_URL (Track B, Sprint B7): a donde se
            # envia una orden de mantenimiento real -- opcional (`None` si el
            # tenant no tiene BayForce configurado todavia), nunca una URL
            # fija en codigo. `send_to_bayforce()` rechaza el envio con un
            # error claro si falta, nunca simula un envio que no ocurrio.
            bayforce_webhook_url=os.environ.get("RENFYGRID_BAYFORCE_WEBHOOK_URL") or None,
        )
