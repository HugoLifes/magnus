"""Qué puede hacer Magnus Code en **este** equipo, dicho sin rodeos.

Programar con un agente pide mucho más que chatear: el modelo tiene que llamar
herramientas muchas veces seguidas y aguantar contextos largos. En un equipo de
4 GiB eso no va a pasar, y prometerlo solo consigue que la persona se decepcione
y desinstale.

Por eso Magnus clasifica cada equipo en un nivel y dice tres cosas:

1. **qué modos puede usar** (Plan, Preguntar, Aceptar ediciones, Autónomo),
2. **qué modelo descargar**, con su tamaño, o que no hay ninguno que quepa,
3. **qué hacer si no alcanza**: otro equipo de tu red o Magnus Cloud, avisando
   de que ahí el código sale de la máquina.

Los niveles no son marketing: salen de la memoria utilizable que ya calcula
`core/catalog.py` y del tamaño real de los modelos del catálogo.
"""

from __future__ import annotations

import enum
import platform
import shutil
from dataclasses import dataclass, field

from core.catalog import CODE, CatalogModel, recommend, usable_gib
from core.code.permissions import Mode
from core.hardware import GPU
from core.platform import PlatformProfile

# Contexto mínimo para trabajar con agentes, según la documentación de Ollama.
MIN_CONTEXT = 32768
# Por debajo de esto el modelo se pierde encadenando herramientas (medido en el
# Jetson: los de menos de 3 B ni siquiera las llaman).
MIN_PARAMS_B = 6.0
# Memoria utilizable a partir de la cual tiene sentido el modo autónomo.
AUTO_MIN_GIB = 14.0


class CodeTier(str, enum.Enum):
    """Nivel del equipo para Magnus Code."""

    EDGE = "edge"        # Jetson, laptops de 4–6 GiB: acompaña, no trabaja solo
    BASIC = "basico"     # 6–12 GiB: edita con permiso, tareas cortas
    CAPABLE = "capaz"    # 12–24 GiB: autónomo con sandbox
    PRO = "pro"          # 24 GiB o más: proyectos grandes y contexto largo


_TIER_LABEL = {
    CodeTier.EDGE: "Equipo de borde",
    CodeTier.BASIC: "Equipo básico",
    CodeTier.CAPABLE: "Equipo capaz",
    CodeTier.PRO: "Equipo profesional",
}


@dataclass(frozen=True)
class CodeCapability:
    """Lo que este equipo puede hacer, y qué le falta para lo demás."""

    tier: CodeTier
    usable_gib: float
    modes: tuple[Mode, ...]
    recommended: CatalogModel | None
    downloaded: bool
    headline: str
    advice: list[str] = field(default_factory=list)

    @property
    def can_autonomous(self) -> bool:
        return Mode.AUTO in self.modes

    def to_dict(self) -> dict:
        return {
            "tier": self.tier.value,
            "tier_label": _TIER_LABEL[self.tier],
            "usable_gib": round(self.usable_gib, 1),
            "modes": [m.value for m in self.modes],
            "can_autonomous": self.can_autonomous,
            "recommended_model": None if self.recommended is None else {
                "id": self.recommended.id,
                "name": self.recommended.name,
                "download_gib": self.recommended.size_gib,
                "params_b": self.recommended.params_b,
                "context": self.recommended.context,
                "downloaded": self.downloaded,
            },
            "headline": self.headline,
            "advice": list(self.advice),
        }


def sandbox_available() -> bool:
    """Si este sistema puede encerrar los comandos del agente.

    Hoy: Linux y el Jetson con `bubblewrap`, y macOS con `sandbox-exec`. En
    Windows todavía no, así que allí no hay modo autónomo: cada comando se
    aprueba a mano (ver `docs/MAGNUS_CODE.md` §5).
    """
    sistema = platform.system()
    if sistema == "Linux":
        return shutil.which("bwrap") is not None
    if sistema == "Darwin":
        return shutil.which("sandbox-exec") is not None
    return False


def tier_for(usable: float) -> CodeTier:
    if usable >= 24:
        return CodeTier.PRO
    if usable >= 12:
        return CodeTier.CAPABLE
    if usable >= 6:
        return CodeTier.BASIC
    return CodeTier.EDGE


def capability_for(
    profile: PlatformProfile,
    gpu: GPU | None = None,
    *,
    local_models: tuple[str, ...] = (),
    sandbox_available: bool = False,
) -> CodeCapability:
    """Qué puede hacer Magnus Code aquí, con qué modelo y qué decirle a la persona."""
    usable = usable_gib(profile, gpu)
    tier = tier_for(usable)

    # El mejor modelo de código que quepa **y** que sirva para trabajar con
    # herramientas: uno de 1.5 B cabe en cualquier lado y no sirve para esto.
    recomendado = _best_code_model(profile, gpu)
    descargado = bool(recomendado and _is_local(recomendado.id, local_models))

    modes = [Mode.PLAN, Mode.ASK]
    if recomendado is not None:
        modes.append(Mode.EDIT)
    if recomendado is not None and usable >= AUTO_MIN_GIB and sandbox_available:
        modes.append(Mode.AUTO)

    advice: list[str] = []
    if recomendado is None:
        headline = (f"{_TIER_LABEL[tier]}: aquí Magnus Code lee y propone, pero no hay "
                    "ningún modelo de código que quepa para trabajar de verdad.")
        advice.append("Usa un equipo de tu red con más memoria: Nube → Tus servidores.")
        advice.append("O Magnus Cloud, sabiendo que en ese caso tu código sale del equipo.")
    else:
        que = "descargado" if descargado else f"{recomendado.size_gib:.1f} GiB de descarga"
        headline = (f"{_TIER_LABEL[tier]}: puedes trabajar con {recomendado.name} ({que}) "
                    f"en {'modo autónomo' if Mode.AUTO in modes else 'modo Preguntar'}.")
        if not descargado:
            advice.append(f"Descárgalo con: magnus fetch {recomendado.id}")
        if recomendado.context < MIN_CONTEXT:
            advice.append(
                f"Ese modelo trae {recomendado.context // 1024}K de contexto y para agentes "
                "conviene 32K o más: las tareas largas se le van a olvidar a la mitad."
            )

    if Mode.AUTO not in modes:
        advice.append(_why_not_auto(usable, sandbox_available, recomendado is not None))

    return CodeCapability(
        tier=tier,
        usable_gib=usable,
        modes=tuple(modes),
        recommended=recomendado,
        downloaded=descargado,
        headline=headline,
        advice=advice,
    )


def _best_code_model(profile: PlatformProfile, gpu: GPU | None) -> CatalogModel | None:
    """El modelo de código más capaz que cabe y que sirve para usar herramientas."""
    for rec in recommend(profile, gpu, CODE):
        if rec.fits and rec.model.params_b >= MIN_PARAMS_B:
            return rec.model
    return None


def _is_local(model_id: str, local_models: tuple[str, ...]) -> bool:
    return any(m == model_id or m == f"{model_id}:latest" for m in local_models)


def _why_not_auto(usable: float, sandbox: bool, hay_modelo: bool) -> str:
    if not hay_modelo:
        return "El modo autónomo necesita un modelo de código que quepa en este equipo."
    if usable < AUTO_MIN_GIB:
        return (f"El modo autónomo pide ~{AUTO_MIN_GIB:.0f} GiB utilizables y aquí hay "
                f"{usable:.1f}: en este equipo Magnus Code va pidiendo permiso, que además "
                "es más seguro.")
    return ("El modo autónomo necesita el sandbox activo; en este sistema todavía no está, "
            "así que cada comando se aprueba a mano.")
