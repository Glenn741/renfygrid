"""Firma de ordenes de control (F28, Sprint 7) -- evita que un mensaje
interceptado o repetido en el bus dispare una desconexion
(docs/02-arquitectura-general.md SS6, punto 2).

HMAC-SHA256 sobre los campos esenciales de la orden, con libreria estandar
-- mismo enfoque que `renmeter_common/auth.py` (JWT propio, sin dependencia
externa). El secreto de firma es un parametro (no vive en BD ni en codigo
aca): lo inyecta el llamador desde donde sea que RenfyGrid termine
guardando secretos por tenant (variable de entorno / secreto de k8s en un
entorno real, ver 0002_app_role.sql para el mismo criterio con contraseñas).
"""

from __future__ import annotations

import hashlib
import hmac


def _message(order_id: str, meter_id: str, order_type: str) -> bytes:
    return f"{order_id}:{meter_id}:{order_type}".encode()


def sign_order(order_id: str, meter_id: str, order_type: str, secret: str) -> str:
    return hmac.new(secret.encode(), _message(order_id, meter_id, order_type), hashlib.sha256).hexdigest()


def verify_order_signature(order_id: str, meter_id: str, order_type: str, signature: str, secret: str) -> bool:
    expected = sign_order(order_id, meter_id, order_type, secret)
    return hmac.compare_digest(expected, signature)
