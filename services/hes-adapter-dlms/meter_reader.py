"""Orquestacion de lectura: toma una DlmsSession ya asociada, lee un registro
COSEM (por su codigo OBIS) y devuelve una fila normalizada lista para
raw_reading (services/common: ver docs/03-diseno.md SS1 tabla raw_reading).

Nada de mapeo OBIS fijo aca -- `obis_code`, `attribute_index` y `channel`
llegan como parametros. En un servicio real vienen de `meter_protocol.obis_mapping`
(cacheado con el patron de renmeter_common.config_cache, F06 -- Sprint 2); este
modulo no necesita saber de donde vinieron.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from gurux_dlms.objects import GXDLMSRegister

from dlms_session import DlmsSession


@dataclass
class NormalizedReading:
    meter_id: str
    timestamp: datetime
    channel: str
    value: Any
    source_quality: str = "real"

    def as_row(self) -> dict:
        return {
            "meter_id": self.meter_id,
            "timestamp": self.timestamp,
            "channel": self.channel,
            "value": self.value,
            "source_quality": self.source_quality,
        }


def read_register(
    session: DlmsSession,
    meter_id: str,
    obis_code: str,
    channel: str,
    attribute_index: int = 2,
) -> NormalizedReading:
    """Lee un registro COSEM (ej. energia activa, OBIS '1.0.1.8.0.255') y lo
    normaliza a una lectura de raw_reading. `attribute_index=2` es el atributo
    "value" estandar de un IC 3 (Register) en DLMS -- ver Blue Book de DLMS/COSEM.
    """
    register = GXDLMSRegister(obis_code)
    value = session.read_attribute(register, attribute_index)
    return NormalizedReading(
        meter_id=meter_id,
        timestamp=datetime.now(timezone.utc),
        channel=channel,
        value=value,
    )
