"""Medidor de tokens y coste. Corren SIN GPU."""

from __future__ import annotations

import time

import pytest

from core.metering import (
    CLOUD_PRICES,
    PowerMeter,
    amortization_usd_per_hour,
    cloud_cost_usd,
    integrate_energy_wh,
    meter_turn,
    parse_param_size,
    pick_reference,
    tier_for_params,
)


def test_coste_nube_por_millon():
    price = CLOUD_PRICES["gpt-4o"]
    # 1M de entrada + 1M de salida = 2.50 + 10.00
    assert cloud_cost_usd(price, 1_000_000, 1_000_000) == pytest.approx(12.5)


@pytest.mark.parametrize(
    ("params", "tier"),
    [(0.5, "small"), (1.5, "small"), (4, "small"), (8, "medium"), (32, "large"),
     (70, "large"), (405, "frontier"), (None, "small")],
)
def test_clase_por_tamano(params, tier):
    assert tier_for_params(params) == tier


def test_referencia_auto_y_fija():
    assert pick_reference(1.5).id == "gpt-4o-mini"
    assert pick_reference(70).tier == "large"
    assert pick_reference(1.5, "claude-sonnet-4.5").id == "claude-sonnet-4.5"
    with pytest.raises(ValueError, match="desconocida"):
        pick_reference(8, "modelo-inventado")


def test_amortizacion_jetson():
    # 249 USD en 3 años a 4 h/día ≈ 5.7 centavos por hora.
    assert amortization_usd_per_hour(249, 3, 4) == pytest.approx(0.0568, abs=1e-4)
    assert amortization_usd_per_hour(249, 0, 4) == 0.0


def test_parse_param_size_de_ollama():
    assert parse_param_size("1.5B") == 1.5
    assert parse_param_size("494.03M") == 0.49
    assert parse_param_size("") is None
    assert parse_param_size("raro") is None


def test_turno_completo():
    m = meter_turn(
        model="qwen2.5:1.5b",
        tokens_in=500, tokens_out=300,
        duration_s=10.0, generation_s=6.0, ttft_s=0.8,
        energy_wh=0.02,  # 7.2 W durante 10 s
        avg_power_w=7.2,
        reference=pick_reference(1.5),
        electricity_usd_per_kwh=0.15,
        amortization_per_hour_usd=0.0568,
    )
    assert m.tokens_per_s == 50.0
    # Los costes se redondean a 8 decimales (centésimas de micro-dólar).
    assert m.energy_cost_usd == pytest.approx(0.02 / 1000 * 0.15, abs=1e-8)
    assert m.amortization_cost_usd == pytest.approx(0.0568 * 10 / 3600, abs=1e-8)
    assert m.cloud_cost_usd == pytest.approx((500 * 0.15 + 300 * 0.60) / 1e6, abs=1e-8)
    assert m.savings_usd == pytest.approx(m.cloud_cost_usd - m.local_cost_usd, abs=1e-8)
    assert m.to_dict()["price_table_version"]


def test_turno_sin_sensor_ni_tokens():
    m = meter_turn(model="x", tokens_in=0, tokens_out=0, duration_s=0.0,
                   reference=pick_reference(None))
    assert m.tokens_per_s is None
    assert m.energy_wh is None
    assert m.local_cost_usd == 0.0


def test_integracion_trapecios():
    # 10 W constantes durante 360 s = 1 Wh
    assert integrate_energy_wh([(0.0, 10.0), (360.0, 10.0)]) == pytest.approx(1.0)
    # rampa 0 → 20 W en 360 s = 1 Wh
    assert integrate_energy_wh([(0.0, 0.0), (180.0, 10.0), (360.0, 20.0)]) == pytest.approx(1.0)
    assert integrate_energy_wh([]) is None
    assert integrate_energy_wh([(0.0, 5.0)]) == 0.0


def test_power_meter_muestrea_en_hilo():
    with PowerMeter(lambda: 12.0, interval_s=0.01) as meter:
        time.sleep(0.05)
    assert meter.avg_power_w == pytest.approx(12.0)
    assert meter.energy_wh > 0


def test_power_meter_sensor_que_falla():
    def roto():
        raise OSError("sensor")

    with PowerMeter(roto, interval_s=0.01) as meter:
        time.sleep(0.02)
    assert meter.energy_wh is None and meter.avg_power_w is None
