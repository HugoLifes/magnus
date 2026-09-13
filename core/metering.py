"""Medidor de tokens y coste: cuánto cuesta cada respuesta en local y en la nube.

Es el diferenciador de Magnus. Por turno de chat:

- tokens de entrada y salida — los que reporta el runtime, contados con el
  tokenizer real del modelo (Ollama: `prompt_eval_count` / `eval_count`);
- velocidad (tok/s) y tiempo al primer token;
- energía MEDIDA durante la generación (W de `core.telemetry`), no supuesta;
- coste local = energía × tarifa + amortización del hardware por el tiempo usado;
- coste en la nube del modelo de tamaño comparable, con la tabla de precios
  versionada; y la diferencia: el ahorro.

Todo en USD; la conversión de moneda es cosa de la presentación.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from itertools import pairwise

# ---------------------------------------------------------------------------
# Precios de la nube
# ---------------------------------------------------------------------------

# Precios de lista publicados por cada proveedor, USD por millón de tokens, sin
# descuentos por caché ni por lotes. Cambian: al actualizar, sube la versión
# para que los registros viejos sigan diciendo con qué tabla se calcularon.
PRICE_TABLE_VERSION = "2026-09"


@dataclass(frozen=True)
class CloudPrice:
    id: str
    provider: str
    input_usd_per_mtok: float
    output_usd_per_mtok: float
    # Clase de tamaño con la que se compara un modelo local.
    tier: str


CLOUD_PRICES: dict[str, CloudPrice] = {
    p.id: p
    for p in (
        CloudPrice("gpt-4o-mini", "OpenAI", 0.15, 0.60, "small"),
        CloudPrice("gemini-2.5-flash", "Google", 0.30, 2.50, "medium"),
        CloudPrice("gpt-5-mini", "OpenAI", 0.25, 2.00, "medium"),
        CloudPrice("claude-haiku-4.5", "Anthropic", 1.00, 5.00, "medium"),
        CloudPrice("gpt-4o", "OpenAI", 2.50, 10.00, "large"),
        CloudPrice("gpt-5", "OpenAI", 1.25, 10.00, "large"),
        CloudPrice("gemini-2.5-pro", "Google", 1.25, 10.00, "large"),
        CloudPrice("claude-sonnet-4.5", "Anthropic", 3.00, 15.00, "frontier"),
    )
}

# Con qué modelo de nube se compara cada clase de tamaño local. Se elige el
# más barato razonable de su clase: el ahorro que se anuncia es el conservador.
_REFERENCE_BY_TIER = {
    "small": "gpt-4o-mini",
    "medium": "gemini-2.5-flash",
    "large": "gpt-5",
    "frontier": "claude-sonnet-4.5",
}


def tier_for_params(params_b: float | None) -> str:
    """Clase de tamaño de un modelo local por sus parámetros (B)."""
    if params_b is None or params_b <= 4:
        return "small"
    if params_b <= 15:
        return "medium"
    if params_b <= 80:
        return "large"
    return "frontier"


def pick_reference(params_b: float | None, choice: str = "auto") -> CloudPrice:
    """Modelo de nube con el que comparar. `choice` fija uno concreto."""
    if choice != "auto":
        try:
            return CLOUD_PRICES[choice]
        except KeyError as exc:
            known = ", ".join(sorted(CLOUD_PRICES))
            raise ValueError(f"Referencia de nube desconocida: {choice!r}. Opciones: {known}") from exc
    return CLOUD_PRICES[_REFERENCE_BY_TIER[tier_for_params(params_b)]]


def cloud_cost_usd(price: CloudPrice, tokens_in: int, tokens_out: int) -> float:
    return (tokens_in * price.input_usd_per_mtok + tokens_out * price.output_usd_per_mtok) / 1e6


# ---------------------------------------------------------------------------
# Coste local
# ---------------------------------------------------------------------------

# Precio de referencia del hardware por familia (USD), para amortizar cuando el
# usuario no dice cuánto pagó. Por GPU en datacenter.
REFERENCE_HARDWARE_USD = {
    "jetson": 249.0,        # Orin Nano Super Developer Kit
    "dgx-spark": 3999.0,
    "geforce-rtx": 1500.0,  # laptop o PC con RTX de gama media
    "workstation": 6000.0,
    "datacenter": 40000.0,  # por GPU
    "unknown": 1000.0,
}


def amortization_usd_per_hour(
    hardware_cost_usd: float, lifetime_years: float, hours_per_day: float
) -> float:
    """Coste del hardware repartido entre las horas de uso de su vida útil."""
    hours = lifetime_years * 365 * hours_per_day
    return hardware_cost_usd / hours if hours > 0 else 0.0


def parse_param_size(text: str | None) -> float | None:
    """'1.5B' → 1.5, '494.03M' → 0.49, de `details.parameter_size` de Ollama."""
    if not text:
        return None
    text = text.strip().upper()
    scale = {"B": 1.0, "M": 1e-3, "K": 1e-6}.get(text[-1:])
    try:
        return round(float(text[:-1]) * scale, 2) if scale else float(text)
    except ValueError:
        return None


@dataclass(frozen=True)
class TurnMetrics:
    model: str
    tokens_in: int
    tokens_out: int
    duration_s: float
    ttft_s: float | None
    tokens_per_s: float | None
    avg_power_w: float | None
    energy_wh: float | None
    energy_cost_usd: float
    amortization_cost_usd: float
    local_cost_usd: float
    cloud_reference: str
    cloud_cost_usd: float
    savings_usd: float
    price_table_version: str = PRICE_TABLE_VERSION

    def to_dict(self) -> dict:
        return asdict(self)


def meter_turn(
    *,
    model: str,
    tokens_in: int,
    tokens_out: int,
    duration_s: float,
    reference: CloudPrice,
    ttft_s: float | None = None,
    generation_s: float | None = None,
    energy_wh: float | None = None,
    avg_power_w: float | None = None,
    electricity_usd_per_kwh: float = 0.15,
    amortization_per_hour_usd: float = 0.0,
) -> TurnMetrics:
    """Mide un turno. Sin sensor de potencia la energía queda en None y cuesta 0."""
    gen = generation_s if generation_s else duration_s
    tps = round(tokens_out / gen, 1) if gen > 0 and tokens_out else None
    energy_cost = (energy_wh or 0.0) / 1000 * electricity_usd_per_kwh
    amortization = amortization_per_hour_usd * duration_s / 3600
    local = energy_cost + amortization
    cloud = cloud_cost_usd(reference, tokens_in, tokens_out)
    return TurnMetrics(
        model=model,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        duration_s=round(duration_s, 3),
        ttft_s=round(ttft_s, 3) if ttft_s is not None else None,
        tokens_per_s=tps,
        avg_power_w=round(avg_power_w, 2) if avg_power_w is not None else None,
        energy_wh=round(energy_wh, 4) if energy_wh is not None else None,
        energy_cost_usd=round(energy_cost, 8),
        amortization_cost_usd=round(amortization, 8),
        local_cost_usd=round(local, 8),
        cloud_reference=reference.id,
        cloud_cost_usd=round(cloud, 8),
        savings_usd=round(cloud - local, 8),
    )


# ---------------------------------------------------------------------------
# Energía medida
# ---------------------------------------------------------------------------


class PowerMeter:
    """Muestrea la potencia en un hilo mientras dura la generación.

    Integra por trapecios: con muestras cada 0.5 s una respuesta de 3 s tiene 7
    puntos, suficiente para una ráfaga de GPU. Se atribuye el consumo total del
    equipo (o de las GPUs), no el incremento sobre reposo: el coste local sale
    por lo alto, nunca por lo bajo.
    """

    def __init__(self, sampler: Callable[[], float | None], interval_s: float = 0.5) -> None:
        self._sampler = sampler
        self._interval = interval_s
        self._samples: list[tuple[float, float]] = []
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def _take(self) -> None:
        try:
            watts = self._sampler()
        except Exception:  # noqa: BLE001 — un sensor que falla no debe tumbar el chat
            watts = None
        if watts is not None:
            self._samples.append((time.monotonic(), watts))

    def _run(self) -> None:
        while not self._stop.wait(self._interval):
            self._take()

    def start(self) -> PowerMeter:
        self._take()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=self._interval * 2)
        self._take()

    def __enter__(self) -> PowerMeter:  # noqa: PYI034 — typing.Self exige 3.11
        return self.start()

    def __exit__(self, *exc: object) -> None:
        self.stop()

    @property
    def energy_wh(self) -> float | None:
        return integrate_energy_wh(self._samples)

    @property
    def avg_power_w(self) -> float | None:
        if not self._samples:
            return None
        return sum(w for _, w in self._samples) / len(self._samples)


def integrate_energy_wh(samples: list[tuple[float, float]]) -> float | None:
    """Energía en Wh de muestras (t en s, W), por trapecios."""
    if not samples:
        return None
    if len(samples) == 1:
        return 0.0
    joules = sum((t1 - t0) * (w0 + w1) / 2 for (t0, w0), (t1, w1) in pairwise(samples))
    return joules / 3600
