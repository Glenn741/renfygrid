"""Motor de Balance de Red -- calculo de los KPIs derivados de la matriz de
Balance Hidrico IWA (Track B, Sprint B1/B2, `docs/07-track-b-alcance-funcional.md`
SS1). Logica pura, sin BD -- mismo principio que `vee_engine.py`/
`consumption_engine.py`: los 5 componentes de la matriz (System Input
Volume, Billed Metered/Unbilled, Unbilled Authorized, Apparent/Real
Losses) llegan ya calculados/medidos por el llamador (propios de
RenfyGrid o de un `POST /network-zones/{id}/balance` externo, ver
`balance_service.py`) -- este modulo solo aplica las formulas del
estandar, nunca inventa un componente que no se le paso.

NRW (Non-Revenue Water) es simple: System Input Volume menos lo que
genera ingreso (Billed, medido o no). Water Losses (Apparent + Real) no
es lo mismo que NRW -- Consumo Autorizado No Facturado (hidrantes, lavado
de redes) tampoco genera ingreso pero tampoco es una "perdida" tecnica.

ILI (Infrastructure Leakage Index) es el KPI que de verdad compara
sistemas de tamanos distintos -- Real Losses actuales sobre el minimo
tecnicamente alcanzable (UARL, formula IWA):

    UARL (litros/dia) = (18 * Lm_km + 0.8 * Nc + 25 * Lp_km) * P_mca

donde Lm = longitud de red, Nc = numero de conexiones, Lp = longitud de
acometidas (a menudo desconocida, se asume 0 -- subestima UARL levemente,
documentado aca, nunca silencioso), P = presion promedio (m.c.a.). Sin
estos 3 insumos de la zona (Lm/Nc/P), ILI queda en `None` -- nunca se
inventa con un supuesto no declarado.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class WaterBalanceInputs:
    system_input_volume: float
    billed_metered_consumption: float = 0.0
    billed_unbilled_consumption: float = 0.0
    unbilled_authorized_consumption: float = 0.0
    apparent_losses: float = 0.0
    real_losses: float = 0.0


@dataclass
class ZoneInfrastructure:
    """Insumos de la zona para UARL -- todos opcionales; si falta alguno,
    `infrastructure_leakage_index` devuelve `None` en vez de adivinar."""

    network_length_km: float | None = None
    num_connections: int | None = None
    avg_pressure_mca: float | None = None
    avg_service_connection_length_km: float | None = None  # Lp, opcional dentro de lo opcional


def non_revenue_water(inputs: WaterBalanceInputs) -> float:
    """NRW = System Input Volume - Billed Authorized Consumption (medido +
    no medido) -- el agua autorizada no facturada (hidrantes, lavado de
    redes) NO genera ingreso pero tampoco es NRW en el sentido de
    "perdida"; el estandar IWA la deja fuera de NRW a proposito."""
    return inputs.system_input_volume - inputs.billed_metered_consumption - inputs.billed_unbilled_consumption


def non_revenue_water_pct(inputs: WaterBalanceInputs) -> float | None:
    """NRW como % del System Input Volume -- la forma en la que de verdad
    se reporta y se compara contra un tope regulatorio (IANC/CRA en
    Colombia: <= 30%, Resolucion 315/2005) -- el volumen bruto solo no
    dice nada sin el tamano del sistema. `None` si `system_input_volume`
    es 0 o negativo (division indefinida, no un 0% falso)."""
    if inputs.system_input_volume <= 0:
        return None
    return (non_revenue_water(inputs) / inputs.system_input_volume) * 100


def balance_check_pct(inputs: WaterBalanceInputs) -> float | None:
    """Cuanto se aleja la suma de los 5 componentes del System Input Volume
    declarado, como % del SIV -- un balance que no cierra (por encima de
    unos pocos puntos porcentuales, normal por redondeo/estimacion) senala
    datos de entrada incompletos o inconsistentes, no un error del motor:
    los 5 componentes se toman tal cual se los pasan, nunca se ajustan
    para que "cuadren" solos. `None` si SIV es 0 o negativo."""
    if inputs.system_input_volume <= 0:
        return None
    declared_total = (
        inputs.billed_metered_consumption + inputs.billed_unbilled_consumption
        + inputs.unbilled_authorized_consumption + inputs.apparent_losses + inputs.real_losses
    )
    return ((inputs.system_input_volume - declared_total) / inputs.system_input_volume) * 100


def water_losses(inputs: WaterBalanceInputs) -> float:
    """Water Losses = Apparent + Real -- la suma de los dos componentes que
    el llamador ya trae medidos/estimados por separado (este modulo no los
    deriva de un residual, a diferencia de un audit Top-Down clasico que
    calcularia Losses = SIV - Authorized Consumption; aca se toma lo que
    el cliente ya reporto para poder distinguir Aparente de Real, que un
    residual agregado no permite)."""
    return inputs.apparent_losses + inputs.real_losses


def unavoidable_annual_real_losses_liters_per_day(zone: ZoneInfrastructure) -> float | None:
    """UARL (formula IWA, litros/dia para TODA la zona) -- `None` si falta
    Lm, Nc o P (los 3 insumos obligatorios; Lp es opcional dentro de eso,
    se asume 0 si no se conoce)."""
    if zone.network_length_km is None or zone.num_connections is None or zone.avg_pressure_mca is None:
        return None
    service_connection_length_km = zone.avg_service_connection_length_km or 0.0
    return (
        18 * zone.network_length_km + 0.8 * zone.num_connections + 25 * service_connection_length_km
    ) * zone.avg_pressure_mca


def infrastructure_leakage_index(
    inputs: WaterBalanceInputs, zone: ZoneInfrastructure, period_days: float
) -> float | None:
    """ILI = CARL / UARL, ambos en litros/dia -- `None` si la zona no tiene
    los insumos de UARL, si `period_days <= 0` (rango de periodo invalido),
    o si UARL da 0 (zona sin longitud/conexiones real, division indefinida)."""
    uarl = unavoidable_annual_real_losses_liters_per_day(zone)
    if uarl is None or uarl == 0 or period_days <= 0:
        return None
    carl_liters_per_day = (inputs.real_losses * 1000) / period_days  # real_losses en m3 -> litros
    return carl_liters_per_day / uarl
