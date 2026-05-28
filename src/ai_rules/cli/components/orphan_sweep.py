"""Centralized orphan symlink sweep component."""

from __future__ import annotations

from pathlib import Path

from ai_rules.cli.context import (
    CliContext,
    Component,
    ComponentPlan,
    ComponentResult,
    OrphanSweepPlan,
)
from ai_rules.config import AGENT_SKILLS_DIRS
from ai_rules.utils import is_managed_target

_FILE_DIRS: list[tuple[Path, str]] = [
    (Path("~/.claude/commands"), "*.md"),
    (Path("~/.claude/agents"), "*.md"),
    (Path("~/.claude/hooks"), "*.py"),
]


def _collect_orphans(config_dir: Path) -> list[Path]:
    """Scan all managed directories and return orphaned symlink paths."""
    orphans: list[Path] = []

    for dir_path, pattern in _FILE_DIRS:
        user_dir = dir_path.expanduser()
        if not user_dir.exists():
            continue

        for item in user_dir.glob(pattern):
            if not item.is_symlink() or item.is_dir():
                continue

            try:
                target = item.resolve()
            except OSError, RuntimeError:
                try:
                    target = item.readlink()
                    if not target.is_absolute():
                        target = item.parent / target
                except OSError, RuntimeError:
                    continue

            if is_managed_target(target, config_dir) and not target.exists():
                orphans.append(item)

    for skills_dir_path in AGENT_SKILLS_DIRS.values():
        user_dir = skills_dir_path.expanduser()
        if not user_dir.exists():
            continue

        for item in user_dir.glob("*"):
            if not item.is_symlink():
                continue
            # is_dir() follows symlinks — False for broken ones; check is_symlink+not exists
            if item.is_dir() or not item.exists():
                pass  # process both live dir symlinks and broken dir symlinks
            else:
                continue  # live non-directory symlink — not a skill dir, skip

            try:
                target = item.resolve()
            except OSError, RuntimeError:
                try:
                    target = item.readlink()
                    if not target.is_absolute():
                        target = item.parent / target
                except OSError, RuntimeError:
                    continue

            if is_managed_target(target, config_dir) and not target.exists():
                orphans.append(item)

    return orphans


class OrphanSweepComponent(Component):
    label = "Orphan Sweep"
    component_id = "orphan-sweep"

    def plan(self, ctx: CliContext) -> ComponentPlan:
        orphans = _collect_orphans(ctx.config_dir)
        return OrphanSweepPlan(has_changes=bool(orphans), orphans=orphans)

    def apply(self, ctx: CliContext, plan: ComponentPlan) -> ComponentResult:
        if not isinstance(plan, OrphanSweepPlan) or not plan.orphans:
            return ComponentResult()

        from ai_rules.cli.display import dim, print_absent, print_success
        from ai_rules.symlinks import remove_symlink

        ctx.console.print("\n[bold cyan]Orphan Sweep[/bold cyan]")
        cleaned = 0

        for orphan_path in sorted(plan.orphans):
            if ctx.dry_run:
                print_absent(f"{orphan_path} {dim('(would remove orphan)')}", indent=2)
            else:
                success, _message = remove_symlink(orphan_path, force=True)
                if success:
                    print_success(f"Removed orphaned symlink: {orphan_path}", indent=2)
                    cleaned += 1

        return ComponentResult(
            ok=True,
            changed=cleaned > 0,
            counts={"cleaned": cleaned},
        )

    def install(self, ctx: CliContext) -> ComponentResult:
        plan = self.plan(ctx)
        return self.apply(ctx, plan)

    def status(self, ctx: CliContext) -> ComponentResult:
        from ai_rules.cli.runner import get_console

        orphans = _collect_orphans(ctx.config_dir)
        if not orphans:
            return ComponentResult()

        console = get_console(ctx)
        console.print("[bold]Orphan Sweep[/bold]")

        for orphan_path in sorted(orphans):
            console.print(f"  {orphan_path!s:<50} [yellow]Orphaned[/yellow]")

        console.print()

        return ComponentResult(ok=False, changed=True)
