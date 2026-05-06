"""Skill lifecycle status component."""

from __future__ import annotations

from ai_rules.agents.base import Agent
from ai_rules.cli.context import CliContext, Component, ComponentResult


class SkillsComponent(Component):
    label = "Skills"

    def status(self, ctx: CliContext) -> ComponentResult:
        all_correct = True
        rendered_header = False

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

            if not rendered_header:
                ctx.console.print("[bold cyan]Skills[/bold cyan]\n")
                rendered_header = True
            ctx.console.print(f"[bold]{target.name}:[/bold]")

            for name in sorted(skill_status.managed_installed.keys()):
                ctx.console.print(
                    f"  {name:<20} [green]Installed[/green] [dim](managed)[/dim]"
                )

            for name, item in sorted(skill_status.managed_wrong_target.items()):
                if item.is_broken:
                    ctx.console.print(
                        f"  {name:<20} [red]Broken symlink[/red] [dim](managed)[/dim]"
                    )
                else:
                    ctx.console.print(
                        f"  {name:<20} [yellow]Wrong target[/yellow] [dim](managed)[/dim]"
                    )
                    if item.actual_source and item.expected_source:
                        from ai_rules.symlinks import get_content_diff

                        diff_output = get_content_diff(
                            item.actual_source, item.expected_source
                        )
                        if diff_output:
                            ctx.console.print(diff_output)
                all_correct = False

            for name in sorted(skill_status.managed_pending.keys()):
                ctx.console.print(
                    f"  {name:<20} [yellow]Not installed[/yellow] [dim](managed)[/dim]"
                )
                all_correct = False

            for name in sorted(skill_status.unmanaged.keys()):
                if name in orphaned_skills:
                    ctx.console.print(f"  {name:<20} [yellow]Orphaned[/yellow]")
                else:
                    ctx.console.print(f"  {name:<20} [dim]Unmanaged[/dim]")

            ctx.console.print()

        return ComponentResult(ok=all_correct, changed=not all_correct)

    def diff(self, ctx: CliContext) -> ComponentResult:
        return self.status(ctx)
