"""`magnus` — punto de entrada de la CLI.

Comandos implementados:
    Fase 0:
      magnus hardware                 GPUs detectadas en esta máquina
      magnus models                   modelos del registro
      magnus check <modelo> [opts]    ¿cabe el modelo en un destino?
      magnus quants <modelo> [opts]   analiza todas las cuantizaciones
      magnus pull <repo>              descarga modelo desde Hugging Face
      magnus serve                    arranca el daemon (FastAPI)
    Fase 1:
      magnus load <model>             carga un modelo en VRAM via Ollama
      magnus unload <model>           libera un modelo de VRAM
      magnus ps                       modelos cargados en VRAM ahora mismo

Diseño: la CLI no contiene lógica de negocio. Todo vive en `core`. Esto permite
que el daemon y, después, los clientes Flutter reutilicen exactamente lo mismo.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from core import (
    HARDWARE_PRESETS,
    RuntimeBackend,
    RuntimeManager,
    RuntimeManagerError,
    check_fit,
    detect_gpus,
    download_model,
    get_model,
    hf_cli_available,
    quant_matrix,
    recommend_quant,
    resolve_target_vram_gb,
    unified_memory_note,
)
from core.chat import ChatError, ChatService, OllamaChatClient
from core.config import data_dir, load_settings
from core.model_registry import MODEL_REGISTRY
from core.persona import PERSONAS, get_persona
from core.platform import detect_platform
from core.store import Store
from core.telemetry import sample_system

app = typer.Typer(add_completion=False, help="Magnus — SO de agentes local-first sobre NVIDIA.")

# La consola de Windows arranca en cp1252: sin esto los acentos y los símbolos
# (°C, ·, ✓) salen como "�" en las laptops, que son el público principal.
if sys.platform == "win32":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

console = Console()


def _fmt(value: float | None, unit: str = "") -> str:
    return "—" if value is None else f"{value}{unit}"


def _usd(value: float) -> str:
    return f"${value:.6f}"


def _print_metrics(m: dict) -> None:
    saving = m["savings_usd"]
    verdict = (f"[green]ahorro {_usd(saving)}[/green]" if saving >= 0
               else f"[yellow]sobrecoste {_usd(-saving)}[/yellow]")
    parts = [
        f"{m['tokens_in']}→{m['tokens_out']} tok",
        f"{_fmt(m['tokens_per_s'])} tok/s",
        f"1er token {_fmt(m['ttft_s'], ' s')}",
        f"{_fmt(m['energy_wh'], ' Wh')}",
        f"local {_usd(m['local_cost_usd'])}",
        f"nube ({m['cloud_reference']}) {_usd(m['cloud_cost_usd'])}",
    ]
    console.print(f"[dim]{' · '.join(parts)} ·[/dim] {verdict}")


skill_app = typer.Typer(help="Skills: instrucciones reutilizables que se aplican en el chat.")
app.add_typer(skill_app, name="skill")


def _skill_registry():
    # Import perezoso: PyYAML solo hace falta en los comandos de skills y chat.
    from core.skills import BUILTIN_SKILLS_DIR, SkillRegistry

    return SkillRegistry(data_dir() / "skills", BUILTIN_SKILLS_DIR)


@skill_app.command("list")
def skill_list() -> None:
    """Skills disponibles: las incluidas con Magnus y las tuyas."""
    registry = _skill_registry()
    table = Table(title="Skills")
    for col in ("Nombre", "Origen", "Disparadores", "Descripción"):
        table.add_column(col)
    for s in registry.list():
        origin = "incluida" if s.source == "builtin" else "tuya"
        table.add_row(f"/{s.name}", origin, ", ".join(s.triggers) or "—", s.description)
    console.print(table)
    for folder, error in registry.errors.items():
        console.print(f"[yellow]• {folder}: {error}[/yellow]")
    console.print(f"[dim]Tus skills viven en {registry.user_dir}[/dim]")


@skill_app.command("show")
def skill_show(name: str = typer.Argument(..., help="Nombre de la skill.")) -> None:
    """Muestra una skill completa."""
    skill = _skill_registry().get(name)
    if skill is None:
        console.print(f"[red]No existe la skill '{name}'.[/red]")
        raise typer.Exit(code=1)
    console.print(f"[bold]/{skill.name}[/bold] — {skill.description}")
    console.print(f"[dim]Disparadores: {', '.join(skill.triggers) or '—'} · {skill.path}[/dim]\n")
    console.out(skill.body, highlight=False)


@skill_app.command("new")
def skill_new(
    name: str = typer.Argument(..., help="Nombre en minúsculas con guiones, p. ej. 'correo-formal'."),
    description: str = typer.Option(..., "--descripcion", "-d", help="Para qué sirve."),
    triggers: list[str] = typer.Option(None, "--disparador", "-t",
                                       help="Palabra que la activa (repetible)."),
) -> None:
    """Crea una skill tuya con una plantilla lista para editar."""
    from core.skills import SkillError, build_skill

    registry = _skill_registry()
    body = ("Escribe aquí las instrucciones que debe seguir el modelo cuando se use esta "
            "skill.\n\n- Qué hacer\n- Qué evitar\n- Formato de la respuesta\n")
    try:
        saved = registry.save(build_skill(name, description, body, triggers or []))
    except SkillError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1)
    console.print(f"[green]✓ Skill /{saved.name} creada[/green] en {saved.path}")
    console.print(f"[dim]Edítala con: magnus skill edit {saved.name}[/dim]")


@skill_app.command("edit")
def skill_edit(name: str = typer.Argument(..., help="Nombre de la skill.")) -> None:
    """Abre el SKILL.md en tu editor. Los cambios valen en el siguiente mensaje."""
    import click

    skill = _skill_registry().get(name)
    if skill is None or skill.path is None:
        console.print(f"[red]No existe la skill '{name}'.[/red]")
        raise typer.Exit(code=1)
    if skill.source == "builtin":
        console.print("[yellow]Es una skill incluida: crea una tuya con el mismo nombre para "
                      "cambiarla (magnus skill new).[/yellow]")
        raise typer.Exit(code=1)
    click.edit(filename=skill.path)
    registry = _skill_registry()
    if name in registry.errors:
        console.print(f"[red]La skill quedó con errores: {registry.errors[name]}[/red]")


@skill_app.command("test")
def skill_test(message: str = typer.Argument(..., help="Mensaje de prueba.")) -> None:
    """Qué skills se aplicarían a un mensaje, sin llamar al modelo."""
    matched = _skill_registry().resolve(message)
    if not matched:
        console.print("[dim]Ninguna skill aplica a ese mensaje.[/dim]")
        return
    for s in matched:
        console.print(f"[green]/{s.name}[/green] — {s.description}")


rag_app = typer.Typer(help="Colecciones de tus documentos para responder con tus datos.")
app.add_typer(rag_app, name="rag")
mem_app = typer.Typer(help="Memoria: hechos cortos que Magnus recuerda de ti.")
app.add_typer(mem_app, name="mem")


def _rag_store():
    # Import perezoso, como en las skills: solo estos comandos lo necesitan.
    from core.rag import OllamaEmbedder, RagStore

    settings = load_settings()
    manager = RuntimeManager(ollama_url=settings.ollama_url)
    return RagStore(
        data_dir() / "magnus.db",
        lambda model: OllamaEmbedder(settings.ollama_url, model, before=manager.ensure_loaded),
    )


def _fail(exc: Exception) -> typer.Exit:
    console.print(f"[red]{exc}[/red]")
    return typer.Exit(code=1)


@rag_app.command("new")
def rag_new(
    name: str = typer.Argument(..., help="Nombre de la colección, p. ej. 'manuales'."),
    embedding_model: str = typer.Option("nomic-embed-text", "--modelo",
                                        help="Modelo de embeddings de Ollama."),
    chunk_chars: int = typer.Option(1000, "--fragmento", help="Caracteres por fragmento."),
    overlap_chars: int = typer.Option(150, "--solape", help="Caracteres de solapamiento."),
) -> None:
    """Crea una colección de documentos."""
    from core.rag import RagError

    try:
        coll = _rag_store().create_collection(name, embedding_model, chunk_chars, overlap_chars)
    except RagError as exc:
        raise _fail(exc) from exc
    console.print(f"[green]✓ Colección '{coll.name}' creada.[/green] "
                  f"Añade documentos con: magnus rag add {coll.name} <carpeta>")


@rag_app.command("list")
def rag_list() -> None:
    """Colecciones con cuántos documentos y fragmentos tienen."""
    table = Table(title="Colecciones")
    for col in ("Nombre", "Documentos", "Fragmentos", "Embeddings"):
        table.add_column(col)
    for c in _rag_store().list_collections():
        table.add_row(c.name, str(c.documents), str(c.chunks), c.embedding_model)
    console.print(table)


@rag_app.command("add")
def rag_add(
    collection: str = typer.Argument(..., help="Colección."),
    paths: list[str] = typer.Argument(..., help="Archivos o carpetas."),
) -> None:
    """Indexa archivos o carpetas (txt, md, código, html, csv, json; PDF con pypdf)."""
    from pathlib import Path

    from core.rag import RagError

    store = _rag_store()
    for path in paths:
        console.print(f"Indexando {path}…")
        try:
            r = store.ingest_path(collection, Path(path))
        except RagError as exc:
            raise _fail(exc) from exc
        console.print(f"[green]✓ {r['indexed']} nuevos[/green], {r['skipped']} ya estaban, "
                      f"{r['chunks']} fragmentos")
        for file, error in r["errors"].items():
            console.print(f"[yellow]• {file}: {error}[/yellow]")


@rag_app.command("search")
def rag_search(
    collection: str = typer.Argument(..., help="Colección."),
    query: str = typer.Argument(..., help="Qué buscar."),
    k: int = typer.Option(5, "-k", help="Resultados."),
) -> None:
    """Busca por significado en una colección, sin llamar al modelo de chat."""
    from core.rag import RagError

    try:
        hits = _rag_store().search(collection, query, k)
    except RagError as exc:
        raise _fail(exc) from exc
    for i, h in enumerate(hits, 1):
        console.print(f"[bold]{i}. {h.title}[/bold] [dim]({h.score:.3f})[/dim]")
        console.out(h.text[:300] + ("…" if len(h.text) > 300 else ""), highlight=False)
        console.print()


@rag_app.command("rm")
def rag_rm(
    collection: str = typer.Argument(..., help="Colección."),
    yes: bool = typer.Option(False, "--si", help="No pedir confirmación."),
) -> None:
    """Borra una colección y sus fragmentos (tus archivos no se tocan)."""
    from core.rag import RagError

    if not yes and not typer.confirm(f"¿Borrar la colección '{collection}'?"):
        raise typer.Exit()
    try:
        _rag_store().delete_collection(collection)
    except RagError as exc:
        raise _fail(exc) from exc
    console.print(f"[green]✓ Colección '{collection}' borrada.[/green]")


@mem_app.command("add")
def mem_add(text: str = typer.Argument(..., help="Hecho a recordar.")) -> None:
    """Guarda un hecho corto, p. ej. 'Trabajo con un Jetson Orin Nano'."""
    from core.rag import RagError

    try:
        memory = _rag_store().add_memory(text)
    except RagError as exc:
        raise _fail(exc) from exc
    console.print(f"[green]✓ Recordado (#{memory.id}).[/green]")


@mem_app.command("list")
def mem_list() -> None:
    """Todo lo que Magnus recuerda."""
    for m in _rag_store().list_memories():
        console.print(f"[dim]#{m.id}[/dim] {m.text}")


@mem_app.command("rm")
def mem_rm(memory_id: int = typer.Argument(..., help="Número de la memoria.")) -> None:
    """Olvida un hecho."""
    if not _rag_store().delete_memory(memory_id):
        console.print(f"[red]No existe la memoria #{memory_id}.[/red]")
        raise typer.Exit(code=1)
    console.print(f"[green]✓ Olvidado #{memory_id}.[/green]")


@mem_app.command("search")
def mem_search(query: str = typer.Argument(..., help="Qué buscar.")) -> None:
    """Busca en la memoria por significado."""
    from core.rag import RagError

    try:
        hits = _rag_store().search_memories(query, k=5)
    except RagError as exc:
        raise _fail(exc) from exc
    for m in hits:
        console.print(f"[dim]#{m.id} ({m.score:.3f})[/dim] {m.text}")


agent_app = typer.Typer(help="Agentes: modelo + instrucciones + herramientas, definidos en YAML.")
app.add_typer(agent_app, name="agent")


def _agent_registry():
    from core.agent import BUILTIN_AGENTS_DIR, AgentRegistry

    return AgentRegistry(data_dir() / "agents", BUILTIN_AGENTS_DIR)


@agent_app.command("list")
def agent_list() -> None:
    """Agentes disponibles: los incluidos con Magnus y los tuyos."""
    registry = _agent_registry()
    table = Table(title="Agentes")
    for col in ("Nombre", "Origen", "Modelo", "Herramientas", "Descripción"):
        table.add_column(col)
    for a in registry.list():
        table.add_row(a.name, "incluido" if a.source == "builtin" else "tuyo",
                      a.model or "—", ", ".join(a.tools) or "—", a.description)
    console.print(table)
    for name, error in registry.errors.items():
        console.print(f"[yellow]• {name}: {error}[/yellow]")
    console.print(f"[dim]Tus agentes viven en {registry.user_dir}[/dim]")


@agent_app.command("show")
def agent_show(name: str = typer.Argument(..., help="Nombre del agente.")) -> None:
    """Muestra la definición de un agente."""
    from core.agent import render_agent

    spec = _agent_registry().get(name)
    if spec is None:
        console.print(f"[red]No existe el agente '{name}'.[/red]")
        raise typer.Exit(code=1)
    console.print(f"[dim]{spec.path}[/dim]")
    console.out(render_agent(spec), highlight=False)


@agent_app.command("new")
def agent_new(
    name: str = typer.Argument(..., help="Nombre en minúsculas con guiones."),
    description: str = typer.Option(..., "--descripcion", "-d", help="Para qué sirve."),
    model: str = typer.Option(None, "--modelo", "-m", help="Modelo de Ollama por omisión."),
    tools: list[str] = typer.Option(None, "--herramienta", "-t",
                                    help="calcular, fecha_hora, buscar_documentos, recordar, "
                                         "buscar_memoria (repetible)."),
    collection: str = typer.Option(None, "--coleccion", "-c",
                                   help="Colección para buscar_documentos."),
) -> None:
    """Crea un agente tuyo; edita después su YAML para afinar las instrucciones."""
    from core.agent import AgentError, build_agent

    data = {"name": name, "description": description, "model": model, "tools": tools or [],
            "collection": collection,
            "system": "Describe aquí cómo debe comportarse el agente y cuándo usar cada "
                      "herramienta."}
    try:
        saved = _agent_registry().save(build_agent(data))
    except AgentError as exc:
        raise _fail(exc) from exc
    console.print(f"[green]✓ Agente '{saved.name}' creado[/green] en {saved.path}")
    console.print(f"[dim]Pruébalo con: magnus agent run {saved.name} \"tu pregunta\"[/dim]")


@agent_app.command("run")
def agent_run(
    name: str = typer.Argument(..., help="Nombre del agente."),
    message: str = typer.Argument(..., help="Qué le pides."),
    model: str = typer.Option(None, "--modelo", "-m", help="Usar otro modelo."),
) -> None:
    """Ejecuta un agente mostrando cada herramienta que usa."""
    from core.agent import AgentError, AgentRunner

    spec = _agent_registry().get(name)
    if spec is None:
        console.print(f"[red]No existe el agente '{name}'.[/red]")
        raise typer.Exit(code=1)
    settings = load_settings()
    manager = RuntimeManager(ollama_url=settings.ollama_url)
    runner = AgentRunner(
        store=Store(data_dir() / "magnus.db"), settings=settings, platform=detect_platform(),
        client=OllamaChatClient(settings.ollama_url),
        power_sampler=lambda: sample_system().power_w, ensure_loaded=manager.ensure_loaded,
        skills=_skill_registry(), rag=_rag_store(),
    )
    try:
        for event in runner.run(spec, message, model=model):
            if event["type"] == "start":
                for note in event["notes"]:
                    console.print(f"[yellow]• {note}[/yellow]")
            elif event["type"] == "tool_call":
                console.print(f"[cyan]→ {event['name']}[/cyan] [dim]{event['arguments']}[/dim]")
            elif event["type"] == "tool_result":
                console.print(f"[dim]  {event['result'][:200]}[/dim]")
            elif event["type"] == "answer":
                console.print()
                console.out(event["content"], highlight=False)
            elif event["type"] == "done":
                m = event["metrics"]
                console.print(f"[dim]{m['steps']} pasos · {m['stop_reason']}[/dim]")
                _print_metrics(m)
    except AgentError as exc:
        raise _fail(exc) from exc


@app.command()
def chat(
    model: str = typer.Argument(..., help="Modelo de Ollama, p. ej. 'qwen2.5:1.5b'."),
    system_prompt: str = typer.Option(None, "--system", "-s", help="Instrucción de sistema."),
    conversation: str = typer.Option(None, "--conversacion", help="Continuar una conversación."),
    collection: str = typer.Option(None, "--coleccion", "-c",
                                   help="Responder con los documentos de esta colección."),
    use_memory: bool = typer.Option(None, "--memoria/--sin-memoria",
                                    help="Usar la memoria (por omisión: según el equipo)."),
    persona: str = typer.Option(None, "--persona", "-p",
                                help="Cómo habla: magnus, directo, mentor, compa, tecnico."),
) -> None:
    """Chatea con un modelo local. Cada respuesta cierra con el medidor de coste."""
    settings = load_settings()
    store = Store(data_dir() / "magnus.db")
    service = ChatService(
        store=store, settings=settings, platform=detect_platform(),
        client=OllamaChatClient(settings.ollama_url),
        power_sampler=lambda: sample_system().power_w,
        # Recarga con guarda de memoria si Ollama expulsó el modelo.
        ensure_loaded=RuntimeManager(ollama_url=settings.ollama_url).ensure_loaded,
        skills=_skill_registry(),
        rag=_rag_store(),
    )
    tono = get_persona(persona or settings.persona)
    console.print(f"[green]Magnus[/green] · {model} · {tono.name.lower()} ({tono.tagline.lower()})"
                  " · escribe /salir para terminar\n")
    conv_id = conversation
    try:
        while True:
            try:
                text = console.input("[bold cyan]tú ›[/bold cyan] ")
            except (EOFError, KeyboardInterrupt):
                break
            if text.strip() in ("/salir", "/exit", "/quit"):
                break
            if not text.strip():
                continue
            try:
                for event in service.stream(model=model, message=text,
                                            conversation_id=conv_id, system=system_prompt,
                                            collection=collection, use_memory=use_memory,
                                            persona=persona):
                    if event["type"] == "start" and (event["skills"] or event["sources"]):
                        used = [f"/{s}" for s in event["skills"]]
                        used += [f"[{s['n']}] {s['title']}" for s in event["sources"]]
                        console.print(f"[dim]usando: {', '.join(used)}[/dim]")
                    if event["type"] == "token":
                        console.out(event["content"], end="", highlight=False)
                    elif event["type"] == "done":
                        conv_id = event["conversation_id"]
                        console.out("")
                        _print_metrics(event["metrics"])
            except ChatError as exc:
                console.print(f"\n[red]{exc}[/red]")
            console.print()
    finally:
        store.close()


@app.command()
def usage() -> None:
    """Totales del medidor: cuánto has generado en local y cuánto te has ahorrado."""
    store = Store(data_dir() / "magnus.db")
    try:
        s = store.usage_summary()
    finally:
        store.close()
    table = Table(title="Uso acumulado")
    for col in ("Modelo", "Turnos", "Tokens in", "Tokens out", "Wh", "Local", "Nube", "Ahorro"):
        table.add_column(col, justify="left" if col == "Modelo" else "right")
    for row in [*s["by_model"], {"model": "TOTAL", **s}]:
        table.add_row(row["model"], str(row["turns"]), str(row["tokens_in"]),
                      str(row["tokens_out"]), f"{row['energy_wh']:.3f}",
                      _usd(row["local_cost_usd"]), _usd(row["cloud_cost_usd"]),
                      _usd(row["savings_usd"]))
    console.print(table)


@app.command("platform")
def platform_cmd() -> None:
    """Familia NVIDIA de esta máquina y cómo conviene servir modelos en ella."""
    p = detect_platform()
    table = Table(title=f"Plataforma: {p.display_name}", show_header=False)
    table.add_row("Familia", p.family.value)
    table.add_row("GPUs", str(p.gpu_count))
    table.add_row("Memoria", f"{p.total_memory_gib} GiB"
                  + (" (unificada con el sistema)" if p.unified_memory else ""))
    table.add_row("Runtimes, por preferencia", ", ".join(rt.value for rt in p.runtimes))
    table.add_row("Modelos cargados a la vez", str(p.max_loaded_models))
    table.add_row("Peticiones en paralelo", str(p.parallel_requests))
    table.add_row("Tamaño sugerido (q4)", f"hasta ~{p.suggested_max_params_b} B")
    console.print(table)
    for note in p.notes:
        console.print(f"[yellow]• {note}[/yellow]")


@app.command()
def system() -> None:
    """Uso de GPU, potencia, temperatura y memoria, ahora mismo."""
    s = sample_system()
    table = Table(title="Sistema")
    table.add_column("#")
    table.add_column("GPU")
    table.add_column("Uso", justify="right")
    table.add_column("W", justify="right")
    table.add_column("°C", justify="right")
    table.add_column("Memoria (GiB)", justify="right")
    for g in s.gpus:
        mem = f"{_fmt(g.memory_used_gib)} / {_fmt(g.memory_total_gib)}"
        table.add_row(str(g.index), g.name, _fmt(g.utilization_pct, " %"),
                      _fmt(g.power_w), _fmt(g.temperature_c), mem)
    console.print(table)
    console.print(f"RAM disponible: {_fmt(s.ram_available_gib)} / {_fmt(s.ram_total_gib)} GiB"
                  f"   ·   Consumo: {_fmt(s.power_w, ' W')}")


@app.command()
def hardware() -> None:
    """Muestra las GPUs NVIDIA detectadas en esta máquina."""
    gpus = detect_gpus()
    if not gpus:
        console.print("[yellow]No se detectó GPU NVIDIA (¿sin nvidia-smi?).[/yellow]")
        console.print(f"Destinos preset disponibles: {', '.join(sorted(HARDWARE_PRESETS))}")
        raise typer.Exit()
    table = Table(title="GPUs detectadas")
    table.add_column("#")
    table.add_column("Nombre")
    table.add_column("Total (GiB)", justify="right")
    table.add_column("Libre (GiB)", justify="right")
    for g in gpus:
        table.add_row(str(g.index), g.name, f"{g.total_gib}", f"{g.free_gib}")
    console.print(table)


@app.command()
def models() -> None:
    """Lista los modelos del registro y sus dimensiones."""
    table = Table(title="Registro de modelos")
    table.add_column("ID")
    table.add_column("Params (B)", justify="right")
    table.add_column("Capas", justify="right")
    table.add_column("Ctx máx", justify="right")
    table.add_column("Arquitectura")
    for spec in MODEL_REGISTRY.values():
        table.add_row(spec.id, f"{spec.params_b}", str(spec.n_layers),
                      f"{spec.context_max}", spec.architecture)
    console.print(table)


@app.command()
def check(
    model: str = typer.Argument(..., help="ID del modelo (ver `magnus models`)."),
    target: str = typer.Option("auto", "--target", "-t",
                               help="Destino: preset (b200, dgx-spark...), GiB, o 'auto'."),
    quant: str = typer.Option("fp16", "--quant", "-q", help="fp16/fp8/q8/q6/q5/q4."),
    context: int = typer.Option(None, "--context", "-c", help="Tokens de contexto."),
    batch: int = typer.Option(1, "--batch", "-b", help="Peticiones concurrentes."),
) -> None:
    """¿Cabe <model> en <target>? Estima VRAM y recomienda cuantización."""
    spec = get_model(model)
    vram = resolve_target_vram_gb(target)
    res = check_fit(spec, vram, quant=quant, context=context, batch=batch)
    if target == "auto":
        gpus = detect_gpus()
        if gpus and gpus[0].unified_memory:
            note = unified_memory_note(res, gpus[0].free_gib)
            if note:
                res.notes.append(note)

    verdict = "[green]✓ ENTRA[/green]" if res.fits else "[red]✗ NO ENTRA[/red]"
    console.print(f"\n{verdict}  {res.model_id} @ {res.quant} | destino {target} ({res.available_gib} GiB)")

    table = Table(show_header=False)
    table.add_row("Pesos", f"{res.weights_gib} GiB")
    table.add_row("KV cache", f"{res.kv_cache_gib} GiB (ctx {res.context}, batch {res.batch})")
    table.add_row("VRAM requerida", f"{res.required_gib} GiB ({res.utilization_pct}% del destino)")
    table.add_row("Margen", f"{res.headroom_gib} GiB")
    table.add_row("Runtimes", ", ".join(rt.value for rt in res.runtimes) or "—")
    console.print(table)

    for note in res.notes:
        console.print(f"[yellow]• {note}[/yellow]")

    if not res.fits:
        rec = recommend_quant(spec, vram, context=context, batch=batch)
        if rec:
            console.print(f"[cyan]→ Sí entraría en [bold]{rec.quant}[/bold] "
                          f"({rec.required_gib} GiB, margen {rec.headroom_gib} GiB).[/cyan]")
        else:
            console.print("[red]→ No entra ni con q4. Necesita multi-GPU o un destino mayor.[/red]")


@app.command()
def quants(
    model: str = typer.Argument(..., help="ID del modelo (ver `magnus models`)."),
    target: str = typer.Option("auto", "--target", "-t",
                               help="Destino: preset (b200, dgx-spark...), GiB, o 'auto'."),
    context: int = typer.Option(None, "--context", "-c", help="Tokens de contexto."),
    batch: int = typer.Option(1, "--batch", "-b", help="Peticiones concurrentes."),
) -> None:
    """Analiza TODAS las cuantizaciones de un modelo en un destino: cuáles entran."""
    spec = get_model(model)
    vram = resolve_target_vram_gb(target)
    rows = quant_matrix(spec, vram, context=context, batch=batch)

    table = Table(title=f"{spec.id} en {target} ({vram} GiB) — análisis de cuantizaciones")
    table.add_column("Cuant")
    table.add_column("VRAM req.", justify="right")
    table.add_column("% destino", justify="right")
    table.add_column("Margen", justify="right")
    table.add_column("¿Entra?")
    table.add_column("Runtimes")
    for r in rows:
        verdict = "[green]✓[/green]" if r.fits else "[red]✗[/red]"
        table.add_row(r.quant, f"{r.required_gib}", f"{r.utilization_pct}%",
                      f"{r.headroom_gib}", verdict,
                      ", ".join(rt.value for rt in r.runtimes) or "—")
    console.print(table)
    console.print("[dim]Nota: que una cuant 'entre' no garantiza que exista un repo prequantizado; "
                  "revisa en HF o descarga el formato concreto con `magnus pull`.[/dim]")


@app.command()
def pull(
    repo: str = typer.Argument(..., help="Repo de HF, p. ej. 'meta-llama/Llama-3.1-8B'."),
    revision: str = typer.Option(None, "--revision", "-r", help="Rama/tag/commit."),
    include: list[str] = typer.Option(None, "--include", "-i",
                                      help="Patrón(es) de archivo, p. ej. '*Q4_K_M*.gguf'."),
    models_dir: str = typer.Option("models", "--dir", help="Carpeta destino."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Muestra el comando sin descargar."),
) -> None:
    """Descarga un modelo desde Hugging Face (envuelve la CLI de HF)."""
    cli = hf_cli_available()
    if cli is None and not dry_run:
        console.print("[red]No se encontró la CLI de Hugging Face.[/red] "
                      "Instala con: [cyan]pip install -U huggingface_hub[cli][/cyan]")
        console.print("[dim]Para repos privados/gated: `hf auth login` o exporta HF_TOKEN.[/dim]")
        raise typer.Exit(code=1)

    res = download_model(repo, models_dir=models_dir, revision=revision,
                         allow_patterns=include, dry_run=dry_run)
    color = "green" if res.ok else "red"
    if dry_run:
        console.print(f"[cyan]Comando:[/cyan] {res.message}")
    else:
        console.print(f"[{color}]{res.message}[/{color}]")


@app.command()
def load(
    model: str = typer.Argument(..., help="Nombre del modelo en Ollama, p. ej. 'llama3.1:8b'."),
    backend: str = typer.Option("ollama", "--backend", "-b", help="Runtime: ollama (hoy)."),
    no_pull: bool = typer.Option(False, "--no-pull", help="No descargar si no está localmente."),
    force: bool = typer.Option(False, "--force",
                               help="Cargar aunque no quepa en la memoria libre (riesgoso)."),
    ollama_url: str = typer.Option("http://127.0.0.1:11434", "--ollama-url", hidden=True),
) -> None:
    """Carga un modelo en VRAM. Si no está en Ollama local, lo descarga primero."""
    mgr = RuntimeManager(ollama_url=ollama_url)
    try:
        rt = RuntimeBackend(backend)
    except ValueError:
        console.print(f"[red]Backend desconocido: {backend!r}. Opciones: ollama[/red]")
        raise typer.Exit(code=1)

    console.print(f"Cargando [bold]{model}[/bold] en {rt.value}…")
    try:
        loaded = mgr.serve(model, backend=rt, pull_if_missing=not no_pull, force=force)
    except RuntimeManagerError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1)

    vram_str = f"{loaded.size_vram_gib} GiB" if loaded.size_vram_gib else "—"
    console.print(f"[green]✓ {loaded.model_id}[/green] cargado en VRAM ({vram_str})")
    for note in loaded.notes:
        console.print(f"[yellow]• {note}[/yellow]")


@app.command()
def fetch(
    model: str = typer.Argument(..., help="Modelo de Ollama, p. ej. 'qwen3:4b'."),
) -> None:
    """Descarga un modelo de Ollama con barra de progreso."""
    # Import perezoso: la barra solo hace falta aquí y la CLI arranca antes.
    from rich.progress import BarColumn, DownloadColumn, Progress, TextColumn, TransferSpeedColumn

    mgr = RuntimeManager(ollama_url=load_settings().ollama_url)
    columns = (TextColumn("{task.description}"), BarColumn(), DownloadColumn(),
               TransferSpeedColumn())
    try:
        with Progress(*columns, console=console) as progress:
            tasks: dict[str, int] = {}
            for event in mgr.pull(model):
                digest, total = event["digest"], event["total"]
                if digest and total:
                    if digest not in tasks:
                        tasks[digest] = progress.add_task(digest.removeprefix("sha256:")[:12],
                                                          total=total)
                    progress.update(tasks[digest], completed=event["completed"] or 0)
                elif event["status"]:
                    progress.console.print(f"[dim]{event['status']}[/dim]")
    except RuntimeManagerError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1)
    console.print(f"[green]✓ {model}[/green] descargado. Pruébalo con: magnus chat {model}")


@app.command()
def catalog(
    capability: str = typer.Option(None, "--capacidad",
                                   help="chat, code, reasoning, vision, tools o embedding."),
) -> None:
    """Modelos recomendados para ESTA máquina: qué cabe y qué no."""
    from core.catalog import evictable_gib, recommend, usable_gib

    gpus = detect_gpus()
    profile = detect_platform(gpus)
    gpu = gpus[0] if gpus else None
    manager = RuntimeManager(ollama_url=load_settings().ollama_url)
    loaded = manager.list_loaded() if manager.ollama_available() else []
    evictable = evictable_gib(profile, [m.size_vram_gib for m in loaded])
    table = Table(title=f"Catálogo para {profile.display_name} "
                        f"({usable_gib(profile, gpu, evictable)} GiB utilizables)")
    for col in ("Modelo", "Params (B)", "Descarga", "Necesita", "Capacidades", "¿Cabe?"):
        table.add_column(col, justify="right" if col in ("Params (B)", "Descarga", "Necesita")
                         else "left")
    for rec in recommend(profile, gpu, capability, evictable):
        m = rec.model
        verdict = "[green]✓[/green]" if rec.fits else ("[yellow]lento[/yellow]" if rec.note
                                                        else "[red]✗[/red]")
        table.add_row(m.id, f"{m.params_b}", f"{m.size_gib} GiB", f"{rec.required_gib} GiB",
                      ", ".join(m.capabilities), verdict)
    console.print(table)
    console.print("[dim]Descarga uno con: magnus fetch <modelo>[/dim]")


@app.command()
def local() -> None:
    """Modelos descargados en Ollama."""
    mgr = RuntimeManager(ollama_url=load_settings().ollama_url)
    if not mgr.ollama_available():
        console.print("[yellow]Ollama no está disponible. ¿Está arrancado?[/yellow]")
        raise typer.Exit(code=1)
    table = Table(title="Modelos descargados")
    for col in ("Modelo", "Tamaño (GiB)", "Parámetros", "Cuantización"):
        table.add_column(col)
    for m in mgr.list_local_models():
        table.add_row(m.model_id, _fmt(m.size_gib), m.parameter_size or "—",
                      m.quantization or "—")
    console.print(table)


@app.command()
def unload(
    model: str = typer.Argument(..., help="Nombre del modelo a descargar de VRAM."),
    backend: str = typer.Option("ollama", "--backend", "-b"),
    delete: bool = typer.Option(False, "--delete", help="Eliminar también del disco de Ollama."),
    ollama_url: str = typer.Option("http://127.0.0.1:11434", "--ollama-url", hidden=True),
) -> None:
    """Libera un modelo de VRAM (sin borrarlo del disco salvo --delete)."""
    mgr = RuntimeManager(ollama_url=ollama_url)
    try:
        rt = RuntimeBackend(backend)
    except ValueError:
        console.print(f"[red]Backend desconocido: {backend!r}.[/red]")
        raise typer.Exit(code=1)

    try:
        mgr.stop(model, backend=rt, delete_local=delete)
    except RuntimeManagerError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1)

    action = "eliminado del disco" if delete else "liberado de VRAM"
    console.print(f"[green]✓ {model}[/green] {action}.")


@app.command()
def ps(
    ollama_url: str = typer.Option("http://127.0.0.1:11434", "--ollama-url", hidden=True),
) -> None:
    """Muestra los modelos cargados en VRAM ahora mismo."""
    mgr = RuntimeManager(ollama_url=ollama_url)

    if not mgr.ollama_available():
        console.print("[yellow]Ollama no está disponible. ¿Está arrancado?[/yellow]")
        console.print("  Ejecuta: [cyan]ollama serve[/cyan]")
        raise typer.Exit()

    loaded = mgr.list_loaded()
    if not loaded:
        console.print("[dim]No hay modelos cargados en VRAM.[/dim]")
        raise typer.Exit()

    table = Table(title="Modelos en VRAM")
    table.add_column("Modelo")
    table.add_column("Backend")
    table.add_column("VRAM (GiB)", justify="right")
    for m in loaded:
        vram_str = f"{m.size_vram_gib}" if m.size_vram_gib else "—"
        table.add_row(m.model_id, m.backend.value, vram_str)
    console.print(table)


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", help="Host del daemon."),
    port: int = typer.Option(8420, help="Puerto del daemon."),
) -> None:
    """Arranca el daemon (API local que consumirán CLI y clientes Flutter)."""
    import uvicorn

    from core.security import bind_error

    token = load_settings().api_token
    error = bind_error(host, token)
    if error:
        console.print(f"[red]{error}[/red]")
        raise typer.Exit(code=1)
    console.print(f"[green]Magnus daemon[/green] en http://{host}:{port}  (docs en /docs)")
    if token:
        console.print("[dim]Protegido con token: los clientes deben enviarlo.[/dim]")
    uvicorn.run("daemon.app:api", host=host, port=port, reload=False)


token_app = typer.Typer(help="Token de acceso para exponer el daemon en la red.")
app.add_typer(token_app, name="token")


@token_app.command("new")
def token_new() -> None:
    """Crea (o reemplaza) el token. Se muestra una sola vez."""
    from core.config import save_settings
    from core.security import generate_token

    token = generate_token()
    save_settings({"api_token": token})
    console.print("[green]✓ Token creado.[/green] Cópialo en Ajustes del cliente; no se volverá a mostrar:")
    console.out(token, highlight=False)
    console.print("[dim]Reinicia `magnus serve` para aplicarlo.[/dim]")


@token_app.command("rm")
def token_rm() -> None:
    """Quita el token: el daemon solo podrá escuchar en loopback."""
    from core.config import save_settings

    save_settings({"api_token": None})
    console.print("[green]✓ Token eliminado.[/green] Reinicia `magnus serve`.")


@app.command("code")
def code_capability() -> None:
    """Qué puede hacer Magnus Code en este equipo (y qué modelo descargar)."""
    from core.code.capability import capability_for, sandbox_available
    from core.hardware import detect_gpus

    gpus = detect_gpus()
    settings = load_settings()
    try:
        locales = tuple(RuntimeManager(ollama_url=settings.ollama_url).list_available())
    except Exception:  # noqa: BLE001 — sin Ollama igual se puede informar
        locales = ()
    cap = capability_for(detect_platform(gpus), gpus[0] if gpus else None,
                         local_models=locales, sandbox_available=sandbox_available())

    console.print(f"[green]{cap.headline}[/green]\n")
    table = Table(title="Magnus Code en este equipo", show_header=False)
    table.add_column("Campo", style="bold")
    table.add_column("Valor")
    table.add_row("Nivel", f"{cap.tier.value} · {cap.usable_gib} GiB utilizables")
    table.add_row("Modos", ", ".join(m.value for m in cap.modes))
    if cap.recommended:
        estado = "descargado" if cap.downloaded else f"{cap.recommended.size_gib} GiB de descarga"
        table.add_row("Modelo", f"{cap.recommended.name} ({cap.recommended.id}) · {estado}")
        table.add_row("Contexto", f"{cap.recommended.context // 1024}K")
    console.print(table)
    for consejo in cap.advice:
        console.print(f"[dim]· {consejo}[/dim]")


@app.command("persona")
def persona_list() -> None:
    """Personalidades del chat: cómo habla Magnus."""
    actual = load_settings().persona
    table = Table(title="Personalidades")
    table.add_column("id", style="bold")
    table.add_column("Nombre")
    table.add_column("Cómo habla")
    for p in PERSONAS:
        marca = " [green](en uso)[/green]" if p.id == actual else ""
        table.add_row(p.id, p.name, p.tagline + marca)
    console.print(table)
    console.print("[dim]Cámbiala en Ajustes de la app, o por turno: "
                  "magnus chat <modelo> --persona compa[/dim]")


license_app = typer.Typer(help="Licencia de este equipo: plan, activación y emisión.")
app.add_typer(license_app, name="license")


def _license_store():
    from core.config import data_dir
    from core.license import LicenseStore

    return LicenseStore(data_dir())


@license_app.command("show")
def license_show() -> None:
    """Plan activo de este equipo. No sale a internet."""
    from core.license import GRACE_DAYS, plan_allows

    lic = _license_store().current()
    plan = lic.effective_plan()
    table = Table(title="Licencia", show_header=False)
    table.add_column("Campo", style="bold")
    table.add_column("Valor")
    table.add_row("Plan", plan)
    table.add_row("Titular", lic.holder or "—")
    table.add_row("Estado", lic.status())
    if lic.expires:
        dias = lic.days_left()
        vence = time.strftime("%Y-%m-%d", time.localtime(lic.expires))
        table.add_row("Vence", f"{vence} ({dias} días)" if dias is not None else vence)
        if lic.status() == "en gracia":
            table.add_row("Gracia", f"{GRACE_DAYS} días desde el vencimiento")
    else:
        table.add_row("Vence", "no vence")
    table.add_row("Equipos", str(lic.seats))
    console.print(table)
    if not plan_allows(plan, "pro"):
        console.print("[dim]Community. Pro añade tus documentos con citas y el agente de "
                      "código en modo autónomo.[/dim]")


@license_app.command("activate")
def license_activate(
    origen: str = typer.Argument(..., help="Archivo de licencia, o el texto MAGNUS1...."),
) -> None:
    """Activa una licencia firmada. Funciona sin internet."""
    from core.license import LicenseError

    ruta = Path(origen)
    texto = ruta.read_text(encoding="utf-8") if ruta.is_file() else origen
    try:
        lic = _license_store().activate(texto)
    except (LicenseError, OSError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    console.print(f"[green]✓ Licencia activada:[/green] plan {lic.plan} para {lic.holder or 'ti'}.")


@license_app.command("deactivate")
def license_deactivate() -> None:
    """Quita la licencia de este equipo y vuelve a Community."""
    _license_store().deactivate()
    console.print("[green]✓ Licencia quitada.[/green] Este equipo vuelve a Community.")


@license_app.command("keygen")
def license_keygen(
    salida: Path = typer.Option(..., "--salida", help="Dónde guardar la clave PRIVADA."),
) -> None:
    """Crea el par de claves del emisor. La privada nunca va al repo ni a la app."""
    from core.license import generate_keypair

    if salida.exists():
        console.print(f"[red]{salida} ya existe. No se sobrescribe una clave privada.[/red]")
        raise typer.Exit(code=1)
    private, public = generate_keypair()
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(private, encoding="utf-8")
    console.print(f"[green]✓ Clave privada en {salida}[/green] — guárdala en el emisor, nunca aquí.")
    console.print("Clave pública (va en core/license.py o en MAGNUS_LICENSE_PUBKEY):")
    console.out(public, highlight=False)


@license_app.command("issue")
def license_issue(
    clave: Path = typer.Option(..., "--clave", help="Archivo con la clave privada del emisor."),
    titular: str = typer.Option(..., "--titular", help="Nombre o correo de quien compra."),
    plan: str = typer.Option("pro", "--plan", help="community, pro o team."),
    dias: int = typer.Option(365, "--dias", help="Vigencia en días. 0 = no vence."),
    equipos: int = typer.Option(1, "--equipos", help="Equipos que cubre."),
    salida: Path | None = typer.Option(None, "--salida", help="Archivo donde escribir la licencia."),
) -> None:
    """Emite una licencia firmada (ventas en persona y por integradores)."""
    import secrets

    from core.license import PLANS, sign_license

    if plan not in PLANS:
        console.print(f"[red]Plan inválido: {plan}. Válidos: {', '.join(PLANS)}.[/red]")
        raise typer.Exit(code=1)
    ahora = time.time()
    payload = {
        "id": f"MAG-{secrets.token_hex(4).upper()}",
        "plan": plan,
        "holder": titular,
        "issued": round(ahora),
        "expires": None if dias <= 0 else round(ahora + dias * 86400),
        "seats": equipos,
    }
    texto = sign_license(payload, clave.read_text(encoding="utf-8").strip())
    if salida:
        salida.write_text(texto, encoding="utf-8")
        console.print(f"[green]✓ Licencia {payload['id']} en {salida}[/green]")
    else:
        console.out(texto, highlight=False)


@app.command("claude")
def claude_code(
    modelo: str | None = typer.Option(None, "--modelo", help="Modelo local; por omisión, el mejor para código."),
    url: str = typer.Option("http://127.0.0.1:8420", "--url", help="Daemon de Magnus."),
    solo_variables: bool = typer.Option(False, "--solo-variables", help="Solo imprime las variables."),
) -> None:
    """Abre Claude Code contra la GPU de este equipo, a través de Magnus.

    Claude Code habla la API de mensajes de Anthropic; el daemon la expone en
    `/v1/messages` y le pone medidor, guarda de memoria y elección de modelo.
    """
    import shutil
    import subprocess

    token = load_settings().api_token
    entorno = {
        "ANTHROPIC_BASE_URL": url.rstrip("/"),
        "ANTHROPIC_AUTH_TOKEN": token or "magnus",
        "ANTHROPIC_MODEL": modelo or "magnus-auto",
        # Claude Code usa un modelo pequeño para títulos y resúmenes: si no se
        # fija, intenta ir a la nube por él.
        "ANTHROPIC_SMALL_FAST_MODEL": modelo or "magnus-auto",
        # Claude Code pide un contexto grande; los modelos locales rinden mejor
        # sin razonamiento largo en tareas de herramientas.
        "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
    }
    if solo_variables or not shutil.which("claude"):
        if not solo_variables:
            console.print("[yellow]No encontré el comando `claude`.[/yellow] "
                          "Instálalo y vuelve a intentar, o usa estas variables:")
        for clave, valor in entorno.items():
            console.out(f"{clave}={valor}", highlight=False)
        return

    console.print(f"[green]Claude Code contra tu GPU[/green] · daemon {url} · "
                  f"modelo {entorno['ANTHROPIC_MODEL']}")
    console.print("[dim]Cada turno queda en el medidor: `magnus usage`.[/dim]")
    subprocess.run(["claude"], env={**os.environ, **entorno}, check=False)


if __name__ == "__main__":
    app()
