"""Skill lifecycle status component."""

from __future__ import annotations

import os

from pathlib import Path

from ai_rules.agents.base import Agent
from ai_rules.cli.context import (
    CliContext,
    Component,
    ComponentPlan,
    ComponentResult,
    SkillsPlan,
)


class SkillsComponent(Component):
    label = "Skills"
    display_name = "Skills"
    component_id = "skills"

    def plan(self, ctx: CliContext) -> SkillsPlan:
        from ai_rules.config import AGENT_SKILLS_DIRS

        skills_source_dir = ctx.config_dir / "skills"
        if not skills_source_dir.exists():
            return SkillsPlan()

        skill_folders = sorted(
            f
            for f in skills_source_dir.glob("*")
            if f.is_dir() and not f.name.startswith(".")
        )

        symlink_ops: list[tuple[Path, Path]] = []
        cleanup_ops: list[Path] = []
        config_skills_abs = skills_source_dir.resolve()
        seen_dirs: set[Path] = set()

        for target in ctx.selected_targets:
            if not isinstance(target, Agent):
                continue

            if target.agent_id == "shared":
                target_dirs = list(AGENT_SKILLS_DIRS.items())
            elif target.agent_id in AGENT_SKILLS_DIRS:
                target_dirs = [(target.agent_id, AGENT_SKILLS_DIRS[target.agent_id])]
            else:
                continue

            for _agent_id, skills_dir_path in target_dirs:
                user_skills_dir = skills_dir_path.expanduser()
                resolved_dir = user_skills_dir.resolve()
                if resolved_dir in seen_dirs:
                    continue
                seen_dirs.add(resolved_dir)

                for skill_folder in skill_folders:
                    symlink_target = user_skills_dir / skill_folder.name
                    if ctx.config.is_excluded(str(symlink_target)):
                        continue
                    symlink_ops.append((symlink_target, skill_folder))

                if user_skills_dir.exists():
                    for existing in user_skills_dir.iterdir():
                        if not existing.is_symlink():
                            continue
                        try:
                            link_target = existing.resolve()
                        except (OSError, RuntimeError):
                            link_target = None

                        if link_target is None:
                            existing_raw = Path(os.readlink(existing))
                            if not existing_raw.is_absolute():
                                existing_raw = (
                                    existing.parent / existing_raw
                                ).resolve()
                            try:
                                existing_raw.relative_to(config_skills_abs)
                            except ValueError:
                                continue
                            cleanup_ops.append(existing)
                            continue

                        try:
                            link_target.relative_to(config_skills_abs)
                        except ValueError:
                            continue

                        if not link_target.exists():
                            cleanup_ops.append(existing)

        has_changes = bool(symlink_ops or cleanup_ops)
        return SkillsPlan(
            has_changes=has_changes,
            symlink_ops=symlink_ops,
            cleanup_ops=cleanup_ops,
        )

    def apply(self, ctx: CliContext, plan: ComponentPlan) -> ComponentResult:
        if not isinstance(plan, SkillsPlan):
            return ComponentResult()

        from ai_rules.symlinks import SymlinkResult, create_symlink, remove_symlink

        created = 0
        unchanged = 0
        errors = 0

        for symlink_target, skill_folder in plan.symlink_ops:
            result, _msg = create_symlink(
                symlink_target,
                skill_folder,
                force=True,
                dry_run=ctx.dry_run,
            )
            if result == SymlinkResult.ERROR:
                errors += 1
            elif result == SymlinkResult.ALREADY_CORRECT:
                unchanged += 1
            else:
                created += 1

        if not ctx.dry_run:
            for existing in plan.cleanup_ops:
                remove_symlink(existing, force=True)

        return ComponentResult(
            ok=errors == 0,
            changed=created > 0,
            counts={"created": created, "unchanged": unchanged, "errors": errors},
        )

    def install(self, ctx: CliContext) -> ComponentResult:
        import os

        from pathlib import Path

        from ai_rules.config import AGENT_SKILLS_DIRS
        from ai_rules.symlinks import SymlinkResult, create_symlink, remove_symlink

        created = 0
        unchanged = 0
        excluded = 0
        errors = 0

        skills_source_dir = ctx.config_dir / "skills"
        if not skills_source_dir.exists():
            return ComponentResult(ok=True)

        skill_folders = sorted(
            f
            for f in skills_source_dir.glob("*")
            if f.is_dir() and not f.name.startswith(".")
        )

        seen_dirs: set[Path] = set()

        for target in ctx.selected_targets:
            if not isinstance(target, Agent):
                continue

            if target.agent_id == "shared":
                target_dirs = list(AGENT_SKILLS_DIRS.items())
            elif target.agent_id in AGENT_SKILLS_DIRS:
                target_dirs = [(target.agent_id, AGENT_SKILLS_DIRS[target.agent_id])]
            else:
                continue

            for _agent_id, skills_dir_path in target_dirs:
                user_skills_dir = skills_dir_path.expanduser()
                resolved_dir = user_skills_dir.resolve()
                if resolved_dir in seen_dirs:
                    continue
                seen_dirs.add(resolved_dir)

                for skill_folder in skill_folders:
                    symlink_target = user_skills_dir / skill_folder.name
                    if ctx.config.is_excluded(str(symlink_target)):
                        excluded += 1
                        continue

                    result, _msg = create_symlink(
                        symlink_target,
                        skill_folder,
                        force=ctx.yes,
                        dry_run=ctx.dry_run,
                    )
                    if result == SymlinkResult.ERROR:
                        errors += 1
                    elif result == SymlinkResult.ALREADY_CORRECT:
                        unchanged += 1
                    else:
                        created += 1

                if not ctx.dry_run and user_skills_dir.exists():
                    config_skills_abs = skills_source_dir.resolve()
                    for existing in user_skills_dir.iterdir():
                        if not existing.is_symlink():
                            continue
                        try:
                            link_target = existing.resolve()
                        except (OSError, RuntimeError):
                            link_target = None

                        if link_target is None:
                            existing_raw = Path(os.readlink(existing))
                            if not existing_raw.is_absolute():
                                existing_raw = (
                                    existing.parent / existing_raw
                                ).resolve()
                            try:
                                existing_raw.relative_to(config_skills_abs)
                            except ValueError:
                                continue
                            remove_symlink(existing, force=True)
                            continue

                        try:
                            link_target.relative_to(config_skills_abs)
                        except ValueError:
                            continue

                        if not link_target.exists():
                            remove_symlink(existing, force=True)

        return ComponentResult(
            ok=errors == 0,
            changed=created > 0,
            counts={
                "created": created,
                "unchanged": unchanged,
                "excluded": excluded,
                "errors": errors,
            },
        )

    def uninstall(self, ctx: CliContext) -> ComponentResult:
        from ai_rules.config import AGENT_SKILLS_DIRS
        from ai_rules.symlinks import remove_symlink

        removed = 0
        skipped = 0

        skills_source_dir = ctx.config_dir / "skills"
        config_skills_abs = skills_source_dir.resolve()

        for target in ctx.selected_targets:
            if not isinstance(target, Agent):
                continue

            if target.agent_id == "shared":
                target_dirs = list(AGENT_SKILLS_DIRS.items())
            elif target.agent_id in AGENT_SKILLS_DIRS:
                target_dirs = [(target.agent_id, AGENT_SKILLS_DIRS[target.agent_id])]
            else:
                continue

            for _agent_id, skills_dir_path in target_dirs:
                user_skills_dir = skills_dir_path.expanduser()
                if not user_skills_dir.exists():
                    continue

                for existing in user_skills_dir.iterdir():
                    if not existing.is_symlink():
                        continue
                    try:
                        link_target = existing.resolve()
                        link_target.relative_to(config_skills_abs)
                    except (ValueError, OSError, RuntimeError):
                        continue

                    success, _msg = remove_symlink(existing, force=ctx.yes)
                    if success:
                        removed += 1
                    else:
                        skipped += 1

        return ComponentResult(
            changed=removed > 0,
            counts={"removed": removed, "skipped": skipped},
        )

    def status(self, ctx: CliContext) -> ComponentResult:
        from ai_rules.cli.display import dim, print_dim
        from ai_rules.cli.runner import get_console

        console = get_console(ctx)
        all_correct = True

        for target in ctx.selected_targets:
            skill_status = (
                target.get_skill_status() if isinstance(target, Agent) else None
            )
            orphaned_skills = {}
            if skill_status:
                from ai_rules.config import AGENT_SKILLS_DIRS
                from ai_rules.skills import SkillManager

                skill_manager = SkillManager(
                    config_dir=ctx.config_dir,
                    agent_id="" if target.target_id == "shared" else target.target_id,
                    user_skills_dirs=(
                        list(AGENT_SKILLS_DIRS.values())
                        if target.target_id == "shared"
                        else None
                    ),
                )
                orphaned_skills_list = skill_manager.get_orphaned_skills()
                for name, paths in orphaned_skills_list.items():
                    if paths:
                        orphaned_skills[name] = paths[0]

            if not skill_status or not any(
                [
                    skill_status.managed_installed,
                    skill_status.managed_pending,
                    skill_status.managed_wrong_target,
                    skill_status.unmanaged,
                ]
            ):
                continue

            console.print(f"[bold]{target.name}[/bold]")

            for name in sorted(skill_status.managed_installed.keys()):
                console.print(
                    f"  {name:<20} [green]Installed[/green] {dim('(managed)')}"
                )

            for name, item in sorted(skill_status.managed_wrong_target.items()):
                if item.is_broken:
                    console.print(
                        f"  {name:<20} [red]Broken symlink[/red] {dim('(managed)')}"
                    )
                else:
                    console.print(
                        f"  {name:<20} [yellow]Wrong target[/yellow] {dim('(managed)')}"
                    )
                    if item.actual_source and item.expected_source:
                        print_dim(f"Points to {item.actual_source}", indent=4)
                        print_dim(f"Expected: → {item.expected_source}", indent=4)
                        from ai_rules.symlinks import get_content_diff

                        diff_output = get_content_diff(
                            item.actual_source, item.expected_source
                        )
                        if diff_output:
                            console.print(diff_output)
                all_correct = False

            for name in sorted(skill_status.managed_pending.keys()):
                console.print(
                    f"  {name:<20} [yellow]Not installed[/yellow] {dim('(managed)')}"
                )
                all_correct = False

            for name in sorted(skill_status.unmanaged.keys()):
                if name in orphaned_skills:
                    console.print(f"  {name:<20} [yellow]Orphaned[/yellow]")
                else:
                    console.print(f"  {name:<20} {dim('Unmanaged')}")

            console.print()

        return ComponentResult(ok=all_correct, changed=not all_correct)

    def diff(self, ctx: CliContext) -> ComponentResult:
        return self.status(ctx)
