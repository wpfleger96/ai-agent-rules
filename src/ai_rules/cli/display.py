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


def print_error(message: str) -> None:
    get_console().print(f"[red]✗[/red] {message}")


def print_warning(message: str) -> None:
    get_console().print(f"[yellow]⚠[/yellow] {message}")


def print_info(message: str) -> None:
    get_console().print(f"[blue]ℹ[/blue] {message}")


def print_hint(message: str) -> None:
    get_console().print(f"[yellow]💡[/yellow] {message}")
