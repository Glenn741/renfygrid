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

    @classmethod
    def from_env(cls) -> "Settings":
        missing = [
            name
            for name in ("RENFYGRID_DSN", "RENFYGRID_JWT_SECRET", "RENFYGRID_ORDER_SIGNING_SECRET")
            if not os.environ.get(name)
        ]
        if missing:
            raise MissingConfigError(f"Faltan variables de entorno obligatorias: {missing}")
        return cls(
            dsn=os.environ["RENFYGRID_DSN"],
            jwt_secret=os.environ["RENFYGRID_JWT_SECRET"],
            order_signing_secret=os.environ["RENFYGRID_ORDER_SIGNING_SECRET"],
        )
