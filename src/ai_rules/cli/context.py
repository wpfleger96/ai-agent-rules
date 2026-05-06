"""Shared CLI lifecycle context and component primitives."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from rich.console import Console

from ai_rules.agents.base import Agent
from ai_rules.config import Config
from ai_rules.targets.base import ConfigTarget

LifecycleOperation = Literal["install", "status", "diff", "validate", "uninstall"]


@dataclass(frozen=True)
class ComponentResult:
    ok: bool = True
    changed: bool = False
    abort: bool = False
    counts: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class CliContext:
    console: Console
    config_dir: Path
    config: Config
    profile_name: str | None
    all_targets: tuple[ConfigTarget, ...]
    selected_targets: tuple[ConfigTarget, ...]
    target_filter: str | None = None
    yes: bool = False
    dry_run: bool = False
    rebuild_cache: bool = False
    skip_completions: bool = False

    @property
    def selected_agents(self) -> list[Agent]:
        return [target for target in self.selected_targets if isinstance(target, Agent)]

    def selected_target(self, target_id: str) -> ConfigTarget | None:
        return next(
            (
                target
                for target in self.selected_targets
                if target.target_id == target_id
            ),
            None,
        )


class Component:
    label: str

    def install(self, ctx: CliContext) -> ComponentResult:
        return ComponentResult()

    def status(self, ctx: CliContext) -> ComponentResult:
        return ComponentResult()

    def diff(self, ctx: CliContext) -> ComponentResult:
        return ComponentResult()

    def validate(self, ctx: CliContext) -> ComponentResult:
        return ComponentResult()

    def uninstall(self, ctx: CliContext) -> ComponentResult:
        return ComponentResult()
