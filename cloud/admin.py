"""CLI del operador de Magnus Cloud: cuentas, vales y saldos.

    python -m cloud.admin cuenta-nueva "Clínica Norte"
    python -m cloud.admin vales --paquete impulso --cantidad 20
    python -m cloud.admin saldo <id-de-cuenta>
    python -m cloud.admin regalar <id-de-cuenta> 500 --ref cortesia-lanzamiento

Los vales se venden por cualquier medio de cobro (liga de pago, transferencia,
en persona) y el cliente los canjea en la app. Así Magnus Cloud cobra desde el
primer día sin depender aún de una pasarela.
"""

from __future__ import annotations

import os

import typer
from rich.console import Console
from rich.table import Table

from cloud.ledger import Ledger, LedgerError
from cloud.packs import MILLI, PACKS, credits_from_mc

app = typer.Typer(add_completion=False, help="Operador de Magnus Cloud.")
console = Console()

_DB = typer.Option(os.environ.get("MAGNUS_GATEWAY_DB", "ledger.db"), "--db",
                   help="Libro mayor (SQLite).")


@app.command("cuenta-nueva")
def new_account(name: str = typer.Argument(..., help="Nombre del cliente."), db: str = _DB):
    """Crea una cuenta y muestra su clave UNA sola vez."""
    account, key = Ledger(db).create_account(name)
    console.print(f"[green]Cuenta creada[/green] {account.name} · id [bold]{account.id}[/bold]")
    console.print(f"Clave: [bold]{key}[/bold]")
    console.print("[yellow]Guárdala ahora: no se puede volver a mostrar.[/yellow]")


@app.command("vales")
def vouchers(
    paquete: str = typer.Option(..., "--paquete", "-p", help=f"Uno de: {', '.join(PACKS)}"),
    cantidad: int = typer.Option(1, "--cantidad", "-n"),
    db: str = _DB,
):
    """Emite vales canjeables de un paquete."""
    try:
        codes = Ledger(db).create_vouchers(paquete, cantidad)
    except LedgerError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    pack = PACKS[paquete]
    table = Table(title=f"{cantidad} vale(s) · {pack.name} · {pack.credits:,} créditos")
    table.add_column("Código")
    for code in codes:
        table.add_row(code)
    console.print(table)


@app.command("saldo")
def balance(account_id: str, db: str = _DB):
    """Saldo y últimos movimientos de una cuenta."""
    ledger = Ledger(db)
    account = ledger.get_account(account_id)
    if account is None:
        console.print("[red]Cuenta inexistente.[/red]")
        raise typer.Exit(code=1)
    console.print(f"{account.name}: [bold]{credits_from_mc(ledger.balance_mc(account_id)):,}"
                  "[/bold] créditos")
    table = Table()
    for col in ("Movimiento", "Créditos", "Referencia"):
        table.add_column(col)
    for entry in ledger.history(account_id, limit=15):
        table.add_row(entry["kind"], f"{entry['credits']:,}", entry["ref"])
    console.print(table)


@app.command("regalar")
def grant(
    account_id: str,
    creditos: int = typer.Argument(..., help="Positivo suma, negativo resta."),
    ref: str = typer.Option(..., "--ref", help="Referencia única, p. ej. cortesia-sep-2026."),
    motivo: str = typer.Option("ajuste manual", "--motivo"),
    db: str = _DB,
):
    """Suma o resta créditos a mano (cortesías, compensaciones)."""
    ledger = Ledger(db)
    if ledger.get_account(account_id) is None:
        console.print("[red]Cuenta inexistente.[/red]")
        raise typer.Exit(code=1)
    if not ledger.add(account_id, "adjust", creditos * MILLI, ref, {"motivo": motivo}):
        console.print(f"[yellow]La referencia {ref!r} ya estaba aplicada: no se repite.[/yellow]")
        raise typer.Exit(code=1)
    console.print(f"[green]Hecho.[/green] Saldo: {credits_from_mc(ledger.balance_mc(account_id)):,}")


if __name__ == "__main__":
    app()
