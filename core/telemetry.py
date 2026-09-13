"""Telemetría en vivo de GPU y sistema para toda la familia NVIDIA.

Dos fuentes, según el equipo:

- GPU dedicada (GeForce, RTX PRO, datacenter): `nvidia-smi`.
- Jetson: sysfs. `nvidia-smi` no da uso ni potencia ahí, y `tegrastats` no suele
  estar dentro de un contenedor; los archivos de sysfs sí se ven (comprobado en un
  Orin Nano Super, JetPack 6.2, dentro de Docker sin privilegios).

La potencia es lo que permite al medidor calcular el coste de energía real de
cada respuesta en vez de suponerlo.
"""

from __future__ import annotations

import shutil
import subprocess
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from core.hardware import jetson_model, system_memory

# El nombre del nodo cambia entre versiones de L4T; se prueba en orden.
_JETSON_GPU_LOAD = (
    Path("/sys/devices/platform/gpu.0/load"),
    Path("/sys/devices/platform/bus@0/17000000.gpu/load"),
    Path("/sys/devices/platform/17000000.gpu/load"),
)
_INA3221_ROOT = Path("/sys/bus/i2c/drivers/ina3221")
_THERMAL_ROOT = Path("/sys/class/thermal")

_SMI_QUERY = "index,name,utilization.gpu,power.draw,temperature.gpu,memory.total,memory.used"


@dataclass(frozen=True)
class GpuSample:
    index: int
    name: str
    utilization_pct: float | None
    power_w: float | None
    temperature_c: float | None
    memory_total_gib: float | None
    memory_used_gib: float | None
    unified_memory: bool = False


@dataclass(frozen=True)
class SystemSample:
    timestamp: float
    gpus: list[GpuSample]
    ram_total_gib: float | None
    ram_available_gib: float | None
    # Consumo de la placa entera (Jetson: rail VDD_IN). None sin sensor.
    board_power_w: float | None = None
    power_rails_w: dict[str, float] = field(default_factory=dict)

    @property
    def power_w(self) -> float | None:
        """Mejor estimación del consumo atribuible a la inferencia, en W."""
        if self.board_power_w is not None:
            return self.board_power_w
        powers = [g.power_w for g in self.gpus if g.power_w is not None]
        return round(sum(powers), 2) if powers else None

    def to_dict(self) -> dict:
        return asdict(self) | {"power_w": self.power_w}


def _num(value: str) -> float | None:
    """Número de nvidia-smi, o None si viene `[N/A]` / `[Not Supported]`."""
    try:
        return float(value)
    except ValueError:
        return None


def parse_nvidia_smi_telemetry(out: str) -> list[GpuSample]:
    samples: list[GpuSample] = []
    for line in out.strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 7:
            continue
        index = _num(parts[0])
        if index is None:
            continue
        total, used = _num(parts[5]), _num(parts[6])
        samples.append(
            GpuSample(
                index=int(index),
                name=parts[1],
                utilization_pct=_num(parts[2]),
                power_w=_num(parts[3]),
                temperature_c=_num(parts[4]),
                memory_total_gib=round(total / 1024, 2) if total is not None else None,
                memory_used_gib=round(used / 1024, 2) if used is not None else None,
                unified_memory=total is None,
            )
        )
    return samples


def read_power_rails(root: Path = _INA3221_ROOT) -> dict[str, float]:
    """Potencia por rail en W desde los INA3221 del Jetson.

    Cada canal tiene `inN_label`, `inN_input` (mV) y `currN_input` (mA). El canal
    "sum of shunt voltages" no tiene corriente y se descarta. Medido en reposo:
    VDD_IN 4992 mV × 1472 mA = 7.35 W, igual que los 7308 mW de tegrastats.
    """
    rails: dict[str, float] = {}
    for label_file in sorted(root.glob("*/hwmon/hwmon*/in*_label")):
        channel = label_file.name[len("in"):-len("_label")]
        folder = label_file.parent
        try:
            label = label_file.read_text().strip()
            millivolts = float((folder / f"in{channel}_input").read_text())
            milliamps = float((folder / f"curr{channel}_input").read_text())
        except (OSError, ValueError):
            continue
        rails[label] = round(millivolts * milliamps / 1e6, 2)
    return rails


def read_jetson_gpu_load(paths: tuple[Path, ...] = _JETSON_GPU_LOAD) -> float | None:
    """Uso de la GPU del Jetson en %. El archivo va en tanto por mil."""
    for path in paths:
        try:
            return round(float(path.read_text()) / 10, 1)
        except (OSError, ValueError):
            continue
    return None


def read_thermal(zone_type: str, root: Path = _THERMAL_ROOT) -> float | None:
    """Temperatura en °C de la zona térmica con ese tipo (p. ej. `gpu-thermal`)."""
    for zone in sorted(root.glob("thermal_zone*")):
        try:
            if (zone / "type").read_text().strip() != zone_type:
                continue
            return round(float((zone / "temp").read_text()) / 1000, 1)
        except (OSError, ValueError):
            # Algunas zonas (cv0..cv2) responden EAGAIN al leerlas.
            continue
    return None


def _query_nvidia_smi() -> list[GpuSample]:
    try:
        out = subprocess.run(
            ["nvidia-smi", f"--query-gpu={_SMI_QUERY}", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10, check=True,
        ).stdout
    except (subprocess.SubprocessError, OSError):
        return []
    return parse_nvidia_smi_telemetry(out)


def sample_system() -> SystemSample:
    """Una muestra de GPU, memoria y potencia de esta máquina."""
    mem = system_memory()
    total, available = mem if mem else (None, None)
    rails: dict[str, float] = {}
    gpus: list[GpuSample] = []

    model = jetson_model()
    if model:
        rails = read_power_rails()
        used = round(total - available, 2) if mem else None
        gpus = [
            GpuSample(
                index=0,
                name=model,
                utilization_pct=read_jetson_gpu_load(),
                # En el Orin el rail de GPU es compartido con CPU y visión.
                power_w=rails.get("VDD_CPU_GPU_CV"),
                temperature_c=read_thermal("gpu-thermal"),
                memory_total_gib=total,
                memory_used_gib=used,
                unified_memory=True,
            )
        ]
    elif shutil.which("nvidia-smi"):
        gpus = _query_nvidia_smi()

    return SystemSample(
        timestamp=time.time(),
        gpus=gpus,
        ram_total_gib=total,
        ram_available_gib=available,
        board_power_w=rails.get("VDD_IN"),
        power_rails_w=rails,
    )
