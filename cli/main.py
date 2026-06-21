"""`magnus` — punto de entrada de la CLI.

Comandos implementados (Fase 0):
    magnus hardware                 GPUs detectadas en esta máquina
    magnus models                   modelos del registro
    magnus check <modelo> [opts]    ¿cabe el modelo en un destino?
    magnus serve                    arranca el daemon (FastAPI)

Diseño: la CLI no contiene lógica de negocio. Todo vive en `core`. Esto permite
que el daemon y, después, los clientes Flutter reutilicen exactamente lo mismo.
"""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from core import (
    HARDWARE_PRESETS,
    check_fit,
    detect_gpus,
    get_model,
    recommend_quant,
    resolve_target_vram_gb,
)
from core.model_registry import MODEL_REGISTRY

app = typer.Typer(add_completion=False, help="Magnus — SO de agentes local-first sobre NVIDIA.")
console = Console()


@app.command()
def hardware() -> None:
    """Muestra las GPUs NVIDIA detectadas en esta máquina."""
    gpus = detect_gpus()
    if not gpus:
        console.print("[yellow]No se detectó GPU NVIDIA (¿sin nvidia-smi?).[/yellow]")
        console.print(f"Destinos preset disponibles: {', '.join(sorted(HARDWARE_PRESETS))}")
        raise typer.Exit()
    table = Table(title="GPUs detectadas")
    table.add_column("#"); table.add_column("Nombre")
    table.add_column("Total (GiB)", justify="right")
    table.add_column("Libre (GiB)", justify="right")
    for g in gpus:
        table.add_row(str(g.index), g.name, f"{g.total_gib}", f"{g.free_gib}")
    console.print(table)


@app.command()
def models() -> None:
    """Lista los modelos del registro y sus dimensiones."""
    table = Table(title="Registro de modelos")
    table.add_column("ID"); table.add_column("Params (B)", justify="right")
    table.add_column("Capas", justify="right"); table.add_column("Ctx máx", justify="right")
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
