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

import sys

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


@app.command()
def chat(
    model: str = typer.Argument(..., help="Modelo de Ollama, p. ej. 'qwen2.5:1.5b'."),
    system_prompt: str = typer.Option(None, "--system", "-s", help="Instrucción de sistema."),
    conversation: str = typer.Option(None, "--conversacion", help="Continuar una conversación."),
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
    )
    console.print(f"[green]Magnus[/green] · {model} · escribe /salir para terminar\n")
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
                                            conversation_id=conv_id, system=system_prompt):
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
    from core.catalog import recommend, usable_gib

    gpus = detect_gpus()
    profile = detect_platform(gpus)
    gpu = gpus[0] if gpus else None
    table = Table(title=f"Catálogo para {profile.display_name} "
                        f"({usable_gib(profile, gpu)} GiB utilizables)")
    for col in ("Modelo", "Params (B)", "Descarga", "Necesita", "Capacidades", "¿Cabe?"):
        table.add_column(col, justify="right" if col in ("Params (B)", "Descarga", "Necesita")
                         else "left")
    for rec in recommend(profile, gpu, capability):
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

    console.print(f"[green]Magnus daemon[/green] en http://{host}:{port}  (docs en /docs)")
    uvicorn.run("daemon.app:api", host=host, port=port, reload=False)


if __name__ == "__main__":
    app()
