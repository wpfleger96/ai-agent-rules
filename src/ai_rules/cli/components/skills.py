"""Skill lifecycle status component."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from ai_rules.agents.base import Agent
from ai_rules.cli.context import (
    CliContext,
    Component,
    ComponentPlan,
    ComponentResult,
    SkillsPlan,
)
from ai_rules.symlinks import link_entry
from ai_rules.utils import is_managed_target, links_to_source

_SHARED_PARENT = ("ai_rules", "config", "skills")
_PROFILE_PARENT = ("ai_rules", "config", "profiles", "skills")


def _managed_skill_roots(config_dir: Path) -> list[Path]:
    from ai_rules.skills import PROFILE_SKILLS_SUBDIR

    return [
        (config_dir / "skills").resolve(),
        (config_dir / PROFILE_SKILLS_SUBDIR).resolve(),
    ]


def _deployed_from(
    link: Path, target: Path, root: Path, bundled: tuple[str, ...]
) -> bool:
    """True if link is exactly what install creates from root: same name, directly inside it.

    The bundled parent also matches older installs (e.g. a previous site-packages);
    aliases and links into unrelated trees never match.
    """
    parent = target.parent
    return target.name == link.name and (
        parent == root or parent.parts[-len(bundled) :] == bundled
    )


def _stale_skill_links(
    ctx: CliContext, user_skills_dir: Path, wanted: Mapping[str, Path]
) -> list[Path]:
    """Managed skill links install removes, given the ``wanted`` skills it deploys."""
    from ai_rules.skills import SkillManager

    if not user_skills_dir.exists():
        return []
    shared_root, profile_root = _managed_skill_roots(ctx.config_dir)
    install_shapes = ((shared_root, _SHARED_PARENT), (profile_root, _PROFILE_PARENT))
    stale_links = []
    for existing in user_skills_dir.iterdir():
        if not existing.is_symlink():
            continue
        try:
            link_target = link_entry(existing)
        except OSError:
            continue
        if not any(is_managed_target(link_target, root) for root, _ in install_shapes):
            continue
        # Ownership follows the link's install shape, not the checkout it points into.
        # Owned links are judged by current source alone: one into another checkout or
        # an old install goes once source drops the name and is re-pointed otherwise.
        owned = any(
            _deployed_from(existing, link_target, root, bundled)
            for root, bundled in install_shapes
        )
        if owned:
            excluded = ctx.config.is_excluded(str(existing))
            stale = existing.name not in wanted or excluded
        else:
            missing = not link_target.exists()
            stale = missing or SkillManager.is_skill_disabled(link_target)
        if stale:
            stale_links.append(existing)
    return stale_links


class SkillsComponent(Component):
    label = "Skills"
    component_id = "skills"

    @staticmethod
    def _resolve_target_dirs(target: Agent) -> list[tuple[str, Path]] | None:
        from ai_rules.config import get_agent_skills_dirs

        dirs = get_agent_skills_dirs()
        if target.agent_id == "shared":
            return list(dirs.items())
        if target.agent_id in dirs:
            return [(target.agent_id, dirs[target.agent_id])]
        return None

    def plan(self, ctx: CliContext) -> SkillsPlan:
        from ai_rules.skills import deployable_skills

        wanted = deployable_skills(ctx.config_dir, ctx.config.skills)

        symlink_ops: list[tuple[Path, Path]] = []
        cleanup_ops: list[Path] = []
        seen_dirs: set[Path] = set()

        for target in ctx.selected_targets:
            if not isinstance(target, Agent):
                continue

            target_dirs = self._resolve_target_dirs(target)
            if target_dirs is None:
                continue

            for _agent_id, skills_dir_path in target_dirs:
                user_skills_dir = skills_dir_path.expanduser()
                resolved_dir = user_skills_dir.resolve()
                if resolved_dir in seen_dirs:
                    continue
                seen_dirs.add(resolved_dir)

                linked: set[Path] = set()
                for skill_folder in wanted.values():
                    symlink_target = user_skills_dir / skill_folder.name
                    if ctx.config.is_excluded(str(symlink_target)):
                        continue
                    symlink_ops.append((symlink_target, skill_folder))
                    linked.add(symlink_target)

                # A link install (re-)points must never also be removed.
                cleanup_ops.extend(
                    link
                    for link in _stale_skill_links(ctx, user_skills_dir, wanted)
                    if link not in linked
                )

        has_changes = bool(symlink_ops or cleanup_ops)
        return SkillsPlan(
            has_changes=has_changes,
            symlink_ops=symlink_ops,
            cleanup_ops=cleanup_ops,
        )

    def apply(self, ctx: CliContext, plan: ComponentPlan) -> ComponentResult:
        if not isinstance(plan, SkillsPlan):
            return ComponentResult()

        from ai_rules.cli.display import print_success, print_would
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

        removed = 0
        for existing in plan.cleanup_ops:
            if ctx.dry_run:
                print_would(f"Would remove orphaned skill link: {existing}", indent=2)
                removed += 1
            elif remove_symlink(existing, force=True)[0]:
                print_success(f"Removed orphaned skill link: {existing}", indent=2)
                removed += 1

        return ComponentResult(
            ok=errors == 0,
            changed=bool(created or removed),
            counts={
                "created": created,
                "unchanged": unchanged,
                "removed": removed,
                "errors": errors,
            },
        )

    def uninstall(self, ctx: CliContext) -> ComponentResult:
        from ai_rules.symlinks import remove_symlink

        removed = 0
        skipped = 0

        source_dirs = _managed_skill_roots(ctx.config_dir)

        for target in ctx.selected_targets:
            if not isinstance(target, Agent):
                continue

            target_dirs = self._resolve_target_dirs(target)
            if target_dirs is None:
                continue

            for _agent_id, skills_dir_path in target_dirs:
                user_skills_dir = skills_dir_path.expanduser()
                if not user_skills_dir.exists():
                    continue

                for existing in user_skills_dir.iterdir():
                    if not any(
                        links_to_source(existing, d / existing.name)
                        for d in source_dirs
                    ):
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
            orphaned_skills: set[str] = set()
            if skill_status and target.target_id == "shared":
                from ai_rules.config import get_agent_skills_dirs
                from ai_rules.skills import deployable_skills

                wanted = deployable_skills(ctx.config_dir, ctx.config.skills)
                orphaned_skills = {
                    link.name
                    for d in get_agent_skills_dirs().values()
                    for link in _stale_skill_links(ctx, d.expanduser(), wanted)
                }

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
                    all_correct = False
                else:
                    console.print(f"  {name:<20} {dim('Unmanaged')}")

            console.print()

        return ComponentResult(ok=all_correct, changed=not all_correct)
