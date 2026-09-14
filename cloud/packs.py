"""Paquetes de créditos y precio de cada modelo.

Unidad: 1 crédito = 0.001 USD. Así un paquete de $20 son 20,000 créditos y el
cliente ve números redondos, mientras el precio real por token queda en
fracciones de crédito. El libro mayor guarda **milicréditos** (enteros).

Los paquetes grandes regalan créditos: es el incentivo para comprar por
adelantado, que financia el hardware. Los créditos no caducan: caducarlos
genera desconfianza y la ganancia no compensa.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass

USD_PER_CREDIT = 0.001
MILLI = 1000  # milicréditos por crédito

# Bono gratuito por mes calendario, por cuenta. Con un modelo mediano
# (~400 créditos por millón de tokens) alcanza para ~250K tokens: suficiente
# para que "nunca te quedes sin IA" sea cierto sin regalar la GPU.
FREE_MONTHLY_CREDITS = 100


@dataclass(frozen=True)
class Pack:
    id: str
    name: str
    price_usd: float
    credits: int
    bonus_pct: int
    tagline: str
    featured: bool = False

    def to_dict(self) -> dict:
        return asdict(self) | {"price_per_credit_usd": round(self.price_usd / self.credits, 6)}


PACKS: dict[str, Pack] = {
    p.id: p
    for p in (
        Pack("chispa", "Chispa", 5.0, 5_000, 0,
             "Para cuando un modelo no cabe en tu equipo."),
        Pack("impulso", "Impulso", 20.0, 22_000, 10,
             "Un mes de uso diario con modelos grandes.", featured=True),
        Pack("turbo", "Turbo", 50.0, 60_000, 20,
             "Agentes que trabajan toda la jornada."),
        Pack("estudio", "Estudio", 200.0, 260_000, 30,
             "Equipos pequeños y proyectos con clientes."),
    )
}


@dataclass(frozen=True)
class ModelPrice:
    """Precio de venta de un modelo, en créditos por millón de tokens."""

    id: str
    upstream_model: str
    input_credits_per_mtok: float
    output_credits_per_mtok: float
    label: str = ""

    def cost_mc(self, tokens_in: int, tokens_out: int) -> int:
        """Milicréditos de una petición. Redondea hacia arriba: nunca se cobra de menos."""
        credits = (tokens_in * self.input_credits_per_mtok
                   + tokens_out * self.output_credits_per_mtok) / 1e6
        return math.ceil(credits * MILLI)

    def affordable_output_tokens(self, balance_mc: int, tokens_in_estimate: int) -> int:
        """Cuántos tokens de salida paga el saldo, descontada la entrada estimada."""
        left_mc = balance_mc - self.cost_mc(tokens_in_estimate, 0)
        if left_mc <= 0 or self.output_credits_per_mtok <= 0:
            return 0
        return int(left_mc / MILLI * 1e6 / self.output_credits_per_mtok)

    def to_dict(self) -> dict:
        data = asdict(self)
        data.pop("upstream_model")  # detalle interno del operador
        return data


def credits_from_mc(mc: int) -> float:
    return round(mc / MILLI, 3)


def tokens_for_credits(credits: int, price: ModelPrice) -> int:
    """Tokens aproximados que compra un saldo, con 3 de entrada por cada 1 de salida."""
    blended = (3 * price.input_credits_per_mtok + price.output_credits_per_mtok) / 4
    return int(credits / blended * 1e6) if blended > 0 else 0
