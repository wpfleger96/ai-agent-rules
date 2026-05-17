"""Shared CLI lifecycle context and component primitives."""

from __future__ import annotations

from abc import ABC
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar, Literal

from rich.console import Console

from ai_rules.agents.base import Agent
from ai_rules.config import Config
from ai_rules.targets.base import ConfigTarget

LifecycleOperation = Literal[
    "install", "status", "diff", "validate", "uninstall", "plan", "apply"
]


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
    component_filter: tuple[str, ...] | None = None
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


class Component(ABC):
    label: str
    filterable: bool = True

    component_id: ClassVar[str]

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

    def plan(self, ctx: CliContext) -> ComponentPlan:
        return ComponentPlan()

    def apply(self, ctx: CliContext, plan: ComponentPlan) -> ComponentResult:
        return ComponentResult()


@dataclass
class ComponentPlan:
    """Base for all component plans."""

    has_changes: bool = False


@dataclass
class SettingsPlan(ComponentPlan):
    stale_targets: list[ConfigTarget] = field(default_factory=list)
    excluded_symlinks_to_clean: list[Path] = field(default_factory=list)


@dataclass
class OptionalToolsPlan(ComponentPlan):
    pass


@dataclass
class ConfigPlan(ComponentPlan):
    symlink_ops: list[tuple[Path, Path]] = field(default_factory=list)
    excluded_count: int = 0


@dataclass
class SkillsPlan(ComponentPlan):
    symlink_ops: list[tuple[Path, Path]] = field(default_factory=list)
    cleanup_ops: list[Path] = field(default_factory=list)


@dataclass
class ClaudeExtensionsPlan(ComponentPlan):
    symlink_ops: list[tuple[str, Path, Path]] = field(default_factory=list)


@dataclass
class MCPPlan(ComponentPlan):
    install_ops: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    conflict_targets: list[str] = field(default_factory=list)


@dataclass
class PluginPlan(ComponentPlan):
    pass


@dataclass
class CompletionsPlan(ComponentPlan):
    shell: str | None = None
    needs_install: bool = False
