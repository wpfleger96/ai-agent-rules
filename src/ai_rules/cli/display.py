"""Shared console proxy and display helpers.

All CLI output routes through the ``console`` singleton exported here.
During parallel execution, worker threads set ``_console_override`` to a
per-thread ``Console(file=StringIO())`` so that ``console.print()`` writes
to the thread-local buffer transparently — no component code changes needed.
"""

from __future__ import annotations

import contextvars

from typing import Any

from rich.console import Console

_console_override: contextvars.ContextVar[Console | None] = contextvars.ContextVar(
    "_console_override", default=None
)

_real_console = Console()


class _ConsoleProxy:
    """Proxy that routes console calls through a ContextVar override."""

    def __init__(self, real: Console) -> None:
        self._real = real

    def _active(self) -> Console:
        return _console_override.get() or self._real

    def print(self, *args: Any, **kwargs: Any) -> None:
        self._active().print(*args, **kwargs)

    def print_exception(self, *args: Any, **kwargs: Any) -> None:
        self._active().print_exception(*args, **kwargs)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._active(), name)


console: Any = _ConsoleProxy(_real_console)


def get_console() -> Console:
    """Return the active console for the current execution context."""
    return _console_override.get() or _real_console


# ─── Icon constants ──────────────────────────────────────────────────────────

ICON_SUCCESS = "[green]✓[/green]"
ICON_DONE = "[dim]✓[/dim]"
ICON_UNCHANGED = "[dim]•[/dim]"
ICON_SKIPPED = "[dim]○[/dim]"
ICON_ABSENT = "[yellow]○[/yellow]"
ICON_UPDATE = "[yellow]↻[/yellow]"
ICON_ERROR = "[red]✗[/red]"
ICON_WARNING = "[yellow]⚠[/yellow]"
ICON_INFO = "[blue]ℹ[/blue]"
ICON_HINT = "[yellow]💡[/yellow]"
ICON_WOULD = "[dim]→[/dim]"
ICON_ADD = "[green]+[/green]"
ICON_NONE = "[dim]-[/dim]"


# ─── Markup builder ──────────────────────────────────────────────────────────


def dim(text: str) -> str:
    return f"[dim]{text}[/dim]"


# ─── Print helpers ───────────────────────────────────────────────────────────


def print_error(message: str, *, indent: int = 0) -> None:
    get_console().print(f"{' ' * indent}{ICON_ERROR} {message}")


def print_warning(message: str, *, indent: int = 0) -> None:
    get_console().print(f"{' ' * indent}{ICON_WARNING} {message}")


def print_info(message: str, *, indent: int = 0) -> None:
    get_console().print(f"{' ' * indent}{ICON_INFO} {message}")


def print_hint(message: str, *, indent: int = 0) -> None:
    get_console().print(f"{' ' * indent}{ICON_HINT} {message}")


def print_success(message: str, *, indent: int = 0) -> None:
    get_console().print(f"{' ' * indent}{ICON_SUCCESS} {message}")


def print_done(message: str, *, indent: int = 0) -> None:
    get_console().print(f"{' ' * indent}{ICON_DONE} {message}")


def print_unchanged(message: str, *, indent: int = 0) -> None:
    get_console().print(f"{' ' * indent}{ICON_UNCHANGED} {message}")


def print_skipped(message: str, *, indent: int = 0) -> None:
    get_console().print(f"{' ' * indent}{ICON_SKIPPED} {message}")


def print_absent(message: str, *, indent: int = 0) -> None:
    get_console().print(f"{' ' * indent}{ICON_ABSENT} {message}")


def print_update(message: str, *, indent: int = 0) -> None:
    get_console().print(f"{' ' * indent}{ICON_UPDATE} {message}")


def print_would(message: str, *, indent: int = 0) -> None:
    get_console().print(f"{' ' * indent}{ICON_WOULD} {message}")


def print_add(message: str, *, indent: int = 0) -> None:
    get_console().print(f"{' ' * indent}{ICON_ADD} {message}")


def print_progress(message: str, *, indent: int = 0) -> None:
    get_console().print(f"{' ' * indent}[yellow]{message}[/yellow]")


def print_dim(message: str, *, indent: int = 0) -> None:
    get_console().print(f"{' ' * indent}{dim(message)}")


def print_label(key: str, value: str, *, indent: int = 0) -> None:
    get_console().print(f"{' ' * indent}{dim(key + ':')} {value}")
