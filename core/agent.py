"""Runtime de agentes: el usuario declara el suyo en YAML y Magnus lo ejecuta en local.

    agents/<nombre>.yaml

    name: investigador
    description: Responde con tus documentos y cita las fuentes.
    model: qwen3:4b              # opcional: si falta, lo elige quien lo ejecuta
    system: |
      Eres un asistente que...
    skills: [resumir]            # sus instrucciones se suman al system prompt
    tools: [buscar_documentos, buscar_memoria]
    collection: manuales         # colección para buscar_documentos
    max_steps: 6                 # vueltas modelo ↔ herramientas
    max_output_tokens: 4000      # tope de tokens generados en toda la ejecución
    think: false                 # opcional: razonamiento en modelos que razonan

El bucle usa el tool calling nativo de Ollama: en cada paso el modelo responde o
pide herramientas; Magnus las ejecuta, le devuelve el resultado y repite. Solo
hay herramientas incluidas y seguras — ninguna ejecuta comandos ni lee archivos
arbitrarios —: un agente definido por un tercero no puede tocar la máquina.

Como las skills, hay agentes incluidos (`agents/` del repo) y del usuario
(`<carpeta de datos>/agents`), con recarga en caliente.
"""

from __future__ import annotations

import ast
import json
import operator
import re
import threading
import time
from collections.abc import Callable, Iterator
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

import yaml

from core.chat import ChatError, OllamaChatClient
from core.config import Settings
from core.metering import (
    REFERENCE_HARDWARE_USD,
    PowerMeter,
    amortization_usd_per_hour,
    meter_turn,
    pick_reference,
)
from core.platform import PlatformProfile
from core.rag import RagError, RagStore
from core.runtime_manager import RuntimeManagerError
from core.skills import SkillRegistry, compose_system_prompt
from core.store import Store, title_from

BUILTIN_AGENTS_DIR = Path(__file__).resolve().parent.parent / "agents"
_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
_RESULT_CHARS = 4000
# Medido en el Jetson: con qwen3:0.6b ni el asistente usó la calculadora (respondió
# 1890.22 a una cuenta que da 1530) ni el investigador buscó en los documentos.
_MIN_TOOL_PARAMS_B = 3.0


# Una llamada escrita a mano por el modelo: {"name": …, "arguments": {…}}.
_TEXT_CALL = re.compile(r"\{[^{}]*\"name\"\s*:\s*\"(\w+)\"[^{}]*\"arguments\"\s*:\s*(\{.*?\})\s*\}",
                        re.DOTALL)


def _calls_in_text(text: str, allowed: tuple[str, ...]) -> list[dict]:
    """Llamadas a herramientas que el modelo escribió como texto plano.

    Modelos locales con plantillas incompletas responden el JSON de la llamada en
    lugar de emitirla por el protocolo. Se rescata solo si la herramienta es una
    de las que ese agente tiene permitidas: nunca se ejecuta algo que el texto
    invente.
    """
    calls: list[dict] = []
    for match in _TEXT_CALL.finditer(text or ""):
        nombre = match.group(1)
        if nombre not in allowed:
            continue
        try:
            argumentos = json.loads(match.group(2))
        except json.JSONDecodeError:
            continue
        if isinstance(argumentos, dict):
            calls.append({"function": {"name": nombre, "arguments": argumentos}})
    return calls


class AgentError(ValueError):
    """Error con un mensaje para el usuario."""


# ---------------------------------------------------------------------------
# Herramientas
# ---------------------------------------------------------------------------


@dataclass
class ToolContext:
    rag: RagStore | None
    collection: str | None


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    parameters: dict
    run: Callable[[dict, ToolContext], str]

    def schema(self) -> dict:
        return {"type": "function", "function": {
            "name": self.name, "description": self.description, "parameters": self.parameters,
        }}


_OPERATORS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod,
    ast.Pow: operator.pow, ast.USub: operator.neg, ast.UAdd: operator.pos,
}


def safe_calculate(expression: str) -> float | int:
    """Aritmética sin `eval`: solo números y + - * / // % **."""
    def ev(node: ast.AST) -> float | int:
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            return node.value
        if isinstance(node, ast.UnaryOp) and type(node.op) in _OPERATORS:
            return _OPERATORS[type(node.op)](ev(node.operand))
        if isinstance(node, ast.BinOp) and type(node.op) in _OPERATORS:
            left, right = ev(node.left), ev(node.right)
            if isinstance(node.op, ast.Pow) and abs(right) > 100:
                raise ValueError("exponente demasiado grande")
            return _OPERATORS[type(node.op)](left, right)
        raise ValueError("solo se permiten números y operadores aritméticos")

    if len(expression) > 200:
        raise ValueError("expresión demasiado larga")
    return ev(ast.parse(expression.replace("^", "**"), mode="eval"))


def _tool_calculate(args: dict, ctx: ToolContext) -> str:
    return str(safe_calculate(str(args.get("expresion", ""))))


def _tool_now(args: dict, ctx: ToolContext) -> str:
    return datetime.now().astimezone().isoformat(timespec="minutes")


def _tool_search_documents(args: dict, ctx: ToolContext) -> str:
    if ctx.rag is None or not ctx.collection:
        return "Este agente no tiene una colección de documentos configurada."
    k = max(1, min(int(args.get("k", 4)), 8))
    hits = ctx.rag.search(ctx.collection, str(args.get("consulta", "")), k=k)
    if not hits:
        return "No se encontró nada relevante en los documentos."
    return "\n\n".join(f"[{i}] ({h.title}) {h.text}" for i, h in enumerate(hits, 1))


def _tool_remember(args: dict, ctx: ToolContext) -> str:
    if ctx.rag is None:
        return "La memoria no está disponible."
    memory = ctx.rag.add_memory(str(args.get("hecho", "")))
    return f"Guardado en la memoria (#{memory.id})."


def _tool_search_memory(args: dict, ctx: ToolContext) -> str:
    if ctx.rag is None:
        return "La memoria no está disponible."
    hits = ctx.rag.search_memories(str(args.get("consulta", "")), k=5, min_score=0.3)
    return "\n".join(f"- {m.text}" for m in hits) or "No hay nada relacionado en la memoria."


def _params(properties: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": properties, "required": required}


TOOLS: dict[str, Tool] = {t.name: t for t in (
    Tool("calcular", "Calcula una expresión aritmética exacta, p. ej. '(1250*0.16)+80'.",
         _params({"expresion": {"type": "string", "description": "Expresión aritmética."}},
                 ["expresion"]), _tool_calculate),
    Tool("fecha_hora", "Devuelve la fecha y la hora actuales de la máquina.",
         _params({}, []), _tool_now),
    Tool("buscar_documentos", "Busca por significado en los documentos del usuario.",
         _params({"consulta": {"type": "string", "description": "Qué buscar."},
                  "k": {"type": "integer", "description": "Cuántos fragmentos (1-8)."}},
                 ["consulta"]), _tool_search_documents),
    Tool("recordar", "Guarda un hecho corto sobre el usuario para recordarlo después.",
         _params({"hecho": {"type": "string", "description": "El hecho a recordar."}},
                 ["hecho"]), _tool_remember),
    Tool("buscar_memoria", "Busca en lo que se sabe del usuario.",
         _params({"consulta": {"type": "string", "description": "Qué buscar."}},
                 ["consulta"]), _tool_search_memory),
)}


# ---------------------------------------------------------------------------
# Definición
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AgentSpec:
    name: str
    description: str
    system: str
    model: str | None = None
    skills: tuple[str, ...] = ()
    tools: tuple[str, ...] = ()
    collection: str | None = None
    max_steps: int = 6
    max_output_tokens: int = 4000
    think: bool | None = None
    source: str = "user"
    path: str | None = None

    def to_dict(self) -> dict:
        return asdict(self) | {"skills": list(self.skills), "tools": list(self.tools)}


def _str_list(value: object, field: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise AgentError(f"'{field}' debe ser una lista de textos.")
    return tuple(v.strip() for v in value if v.strip())


def build_agent(data: dict, *, source: str = "user", path: str | None = None) -> AgentSpec:
    """Valida un diccionario (del YAML o de la API) y construye el agente."""
    name = data.get("name")
    if not isinstance(name, str) or not _NAME_RE.match(name):
        raise AgentError("El nombre debe ir en minúsculas, con letras, números y guiones: "
                         f"{name!r}")
    description = data.get("description")
    if not isinstance(description, str) or not description.strip():
        raise AgentError("Falta la descripción del agente.")
    system = data.get("system") or ""
    if not isinstance(system, str):
        raise AgentError("'system' debe ser texto.")
    tools = _str_list(data.get("tools"), "tools")
    unknown = [t for t in tools if t not in TOOLS]
    if unknown:
        raise AgentError(f"Herramientas desconocidas: {', '.join(unknown)}. "
                         f"Disponibles: {', '.join(sorted(TOOLS))}.")
    model = data.get("model")
    if model is not None and not isinstance(model, str):
        raise AgentError("'model' debe ser texto.")
    collection = data.get("collection")
    if collection is not None and not isinstance(collection, str):
        raise AgentError("'collection' debe ser texto.")
    think = data.get("think")
    if think is not None and not isinstance(think, bool):
        raise AgentError("'think' debe ser true o false.")
    try:
        max_steps = int(data.get("max_steps", 6))
        max_tokens = int(data.get("max_output_tokens", 4000))
    except (TypeError, ValueError) as exc:
        raise AgentError("'max_steps' y 'max_output_tokens' deben ser números.") from exc
    if not 1 <= max_steps <= 20 or not 100 <= max_tokens <= 100_000:
        raise AgentError("max_steps va de 1 a 20 y max_output_tokens de 100 a 100000.")
    return AgentSpec(
        name=name, description=description.strip(), system=system.strip(),
        model=model or None, skills=_str_list(data.get("skills"), "skills"), tools=tools,
        collection=collection or None, max_steps=max_steps, max_output_tokens=max_tokens,
        think=think, source=source, path=path,
    )


def parse_agent(text: str, *, source: str = "user", path: str | None = None) -> AgentSpec:
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise AgentError(f"El YAML no es válido: {exc}") from exc
    if not isinstance(data, dict):
        raise AgentError("El archivo debe ser una lista de 'clave: valor'.")
    return build_agent(data, source=source, path=path)


def render_agent(spec: AgentSpec) -> str:
    data = {k: v for k, v in spec.to_dict().items()
            if k not in ("source", "path") and v is not None and v != [] and v != ""}
    return yaml.safe_dump(data, allow_unicode=True, sort_keys=False)


class AgentRegistry:
    """Agentes disponibles, con recarga en caliente. Seguro entre hilos."""

    def __init__(self, user_dir: Path, builtin_dir: Path | None = None) -> None:
        self.user_dir = Path(user_dir)
        self.builtin_dir = Path(builtin_dir) if builtin_dir else None
        self._lock = threading.Lock()
        self._agents: dict[str, AgentSpec] = {}
        self._errors: dict[str, str] = {}
        self._signature: tuple | None = None

    def _files(self) -> list[tuple[str, Path]]:
        found = []
        for source, folder in (("builtin", self.builtin_dir), ("user", self.user_dir)):
            if folder and folder.is_dir():
                found += [(source, f) for f in sorted(folder.glob("*.yaml"))]
        return found

    def _refresh(self) -> None:
        with self._lock:
            files = self._files()
            signature = tuple((str(f), f.stat().st_mtime_ns) for _, f in files if f.exists())
            if signature == self._signature:
                return
            agents, errors = {}, {}
            for source, f in files:
                try:
                    spec = parse_agent(f.read_text(encoding="utf-8"), source=source, path=str(f))
                except (OSError, AgentError) as exc:
                    errors[f.stem] = str(exc)
                    continue
                if spec.name != f.stem:
                    errors[f.stem] = f"El nombre '{spec.name}' no coincide con el archivo '{f.name}'."
                    continue
                agents[spec.name] = spec
            self._agents, self._errors, self._signature = agents, errors, signature

    def list(self) -> list[AgentSpec]:
        self._refresh()
        return sorted(self._agents.values(), key=lambda a: a.name)

    def get(self, name: str) -> AgentSpec | None:
        self._refresh()
        return self._agents.get(name)

    @property
    def errors(self) -> dict[str, str]:
        self._refresh()
        return dict(self._errors)

    def save(self, spec: AgentSpec) -> AgentSpec:
        self.user_dir.mkdir(parents=True, exist_ok=True)
        (self.user_dir / f"{spec.name}.yaml").write_text(render_agent(spec), encoding="utf-8")
        saved = self.get(spec.name)
        if saved is None:
            raise AgentError(self._errors.get(spec.name, "No se pudo guardar el agente."))
        return saved

    def delete(self, name: str) -> bool:
        path = self.user_dir / f"{name}.yaml"
        if not _NAME_RE.match(name) or not path.is_file():
            if self.get(name) is not None:
                raise AgentError(f"'{name}' viene incluido con Magnus y no se puede borrar. "
                                 "Crea uno con el mismo nombre para cambiarlo.")
            return False
        path.unlink()
        self._refresh()
        return True


# ---------------------------------------------------------------------------
# Ejecución
# ---------------------------------------------------------------------------


class AgentRunner:
    """Ejecuta un agente: bucle modelo ↔ herramientas, medido y guardado."""

    def __init__(
        self,
        store: Store,
        settings: Settings,
        platform: PlatformProfile,
        client: OllamaChatClient,
        power_sampler: Callable[[], float | None],
        power_interval_s: float = 0.5,
        ensure_loaded: Callable[[str], object] | None = None,
        skills: SkillRegistry | None = None,
        rag: RagStore | None = None,
    ) -> None:
        self._store = store
        self._settings = settings
        self._client = client
        self._power_sampler = power_sampler
        self._power_interval = power_interval_s
        self._ensure_loaded = ensure_loaded
        self._skills = skills
        self._rag = rag
        hardware_cost = settings.hardware_cost_usd
        if hardware_cost is None:
            hardware_cost = (REFERENCE_HARDWARE_USD.get(platform.family.value, 1000.0)
                             * max(platform.gpu_count, 1))
        self._amortization = amortization_usd_per_hour(
            hardware_cost, settings.hardware_lifetime_years, settings.hours_per_day
        )

    def _system_prompt(self, spec: AgentSpec) -> str | None:
        skills = [s for s in (self._skills.get(n) for n in spec.skills) if s] \
            if self._skills else []
        return compose_system_prompt(spec.system, skills)

    def _run_tool(self, spec: AgentSpec, name: str, args: dict) -> str:
        if name not in spec.tools or name not in TOOLS:
            return f"Herramienta no permitida para este agente: {name}"
        try:
            result = TOOLS[name].run(args, ToolContext(self._rag, spec.collection))
        except (RagError, ValueError, TypeError, KeyError, ZeroDivisionError, SyntaxError) as exc:
            # Se le devuelve al modelo: puede corregir los argumentos y reintentar.
            return f"Error al usar {name}: {exc}"
        return result[:_RESULT_CHARS]

    def run(
        self,
        spec: AgentSpec,
        message: str,
        *,
        model: str | None = None,
        conversation_id: str | None = None,
    ) -> Iterator[dict]:
        """Eventos: start, tool_call, tool_result (por paso), answer y done."""
        model = model or spec.model
        if not model:
            raise AgentError(f"El agente '{spec.name}' no define modelo: indica uno.")
        if not message.strip():
            raise AgentError("El mensaje está vacío.")
        conv = None
        if conversation_id:
            conv = self._store.get_conversation(conversation_id)
            if conv is None:
                raise AgentError(f"Conversación no encontrada: {conversation_id}")
        if self._ensure_loaded:
            try:
                self._ensure_loaded(model)
            except RuntimeManagerError as exc:
                raise AgentError(str(exc)) from exc
        if conv is None:
            conv = self._store.create_conversation(model=f"agente:{spec.name}",
                                                   title=title_from(message))

        params_b = self._client.parameter_size_b(model)
        notes = []
        if spec.tools and params_b is not None and params_b < _MIN_TOOL_PARAMS_B:
            notes.append(f"{model} tiene {params_b} B: los modelos de menos de "
                         f"{_MIN_TOOL_PARAMS_B:g} B rara vez usan herramientas de forma fiable. "
                         "Para agentes conviene uno de 4 B o más.")

        messages = [{"role": m.role, "content": m.content}
                    for m in self._store.messages(conv.id)]
        system = self._system_prompt(spec)
        if system:
            messages.insert(0, {"role": "system", "content": system})
        messages.append({"role": "user", "content": message})
        self._store.add_message(conv.id, "user", message)
        tools = [TOOLS[t].schema() for t in spec.tools]

        yield {"type": "start", "conversation_id": conv.id, "agent": spec.name,
               "model": model, "tools": list(spec.tools), "notes": notes}

        tokens_in = tokens_out = 0
        eval_ns = 0
        answer = ""
        trace: list[dict] = []
        stop_reason = "respuesta"
        start = time.monotonic()
        step = 0
        with PowerMeter(self._power_sampler, self._power_interval) as meter:
            for step in range(1, spec.max_steps + 1):
                try:
                    response = self._client.chat_once(model, messages, tools or None,
                                                       think=spec.think)
                except ChatError as exc:
                    raise AgentError(str(exc)) from exc
                tokens_in += response.get("prompt_eval_count") or 0
                tokens_out += response.get("eval_count") or 0
                eval_ns += response.get("eval_duration") or 0
                reply = response.get("message") or {}
                calls = reply.get("tool_calls") or []
                if not calls:
                    # Algunos modelos locales escriben la llamada como texto en
                    # vez de usar el protocolo: su plantilla no emite
                    # `tool_calls`. Si el texto es una llamada válida a una
                    # herramienta que este agente tiene, se ejecuta igual.
                    calls = _calls_in_text(reply.get("content") or "", spec.tools)
                if not calls:
                    answer = (reply.get("content") or "").strip()
                    break
                messages.append({"role": "assistant", "content": reply.get("content") or "",
                                 "tool_calls": calls})
                for call in calls:
                    fn = call.get("function") or {}
                    name = str(fn.get("name", ""))
                    args = fn.get("arguments") or {}
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except json.JSONDecodeError:
                            args = {}
                    yield {"type": "tool_call", "step": step, "name": name, "arguments": args}
                    result = self._run_tool(spec, name, args)
                    yield {"type": "tool_result", "step": step, "name": name, "result": result}
                    trace.append({"step": step, "name": name, "arguments": args,
                                  "result": result[:500]})
                    messages.append({"role": "tool", "content": result, "tool_name": name})
                if tokens_out >= spec.max_output_tokens:
                    stop_reason = "límite de tokens"
                    answer = "Me detuve: se alcanzó el límite de tokens del agente."
                    break
            else:
                stop_reason = "límite de pasos"
                answer = f"No terminé en {spec.max_steps} pasos. Esto es lo que encontré:\n" + \
                    "\n".join(f"- {t['name']}: {t['result'][:200]}" for t in trace[-3:])
        duration = time.monotonic() - start

        metrics = meter_turn(
            model=model, tokens_in=tokens_in, tokens_out=tokens_out, duration_s=duration,
            generation_s=eval_ns / 1e9 if eval_ns else None,
            energy_wh=meter.energy_wh, avg_power_w=meter.avg_power_w,
            reference=pick_reference(params_b, self._settings.cloud_reference),
            electricity_usd_per_kwh=self._settings.electricity_usd_per_kwh,
            amortization_per_hour_usd=self._amortization,
        ).to_dict() | {"agent": spec.name, "steps": step, "stop_reason": stop_reason,
                       "tools_used": [t["name"] for t in trace]}
        saved = self._store.add_message(conv.id, "assistant", answer, metrics)
        yield {"type": "answer", "content": answer}
        yield {"type": "done", "conversation_id": conv.id, "message_id": saved.id,
               "content": answer, "metrics": metrics, "trace": trace}
