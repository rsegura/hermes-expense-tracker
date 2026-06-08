"""ASCII banner for the install wizard."""

from __future__ import annotations

from rich.align import Align
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

X_PROFILE = "https://x.com/emanuel_build"

_HERMES = r"""
[bold cyan]██╗  ██╗███████╗██████╗ ███╗   ███╗███████╗███████╗[/]
[bold cyan]██║  ██║██╔════╝██╔══██╗████╗ ████║██╔════╝██╔════╝[/]
[bold cyan]███████║█████╗  ██████╔╝██╔████╔██║█████╗  ███████╗[/]
[bold cyan]██╔══██║██╔══╝  ██╔══██╗██║╚██╔╝██║██╔══╝  ╚════██║[/]
[bold cyan]██║  ██║███████╗██║  ██║██║ ╚═╝ ██║███████╗███████║[/]
[bold cyan]╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝╚═╝     ╚═╝╚══════╝╚══════╝[/]
"""

_SUBTITLE = "\n[bold gold1]            Expense Tracker[/]\n"

_CREDIT = (
    "\n[dim]built by[/] [bold]@emanuel_build[/] [dim]· follow me on[/] "
    f"[link={X_PROFILE}][bold cyan]X[/][/link] [dim]([/][link={X_PROFILE}]{X_PROFILE}[/link][dim])[/]"
)


def print_install_banner(console: Console) -> None:
    body = Text.from_markup((_HERMES + _SUBTITLE + _CREDIT).strip("\n"))
    console.print()
    console.print(
        Panel(
            Align.center(body),
            border_style="cyan",
            padding=(1, 2),
        )
    )
    console.print()
