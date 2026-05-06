from __future__ import annotations

import sys

import click

from click.shell_completion import CompletionItem

import ai_rules.cli as cli_facade


@click.group()
def skill() -> None:
    """Browse and share bundled skills."""
    pass


def complete_skills(
    ctx: click.Context, param: click.Parameter, incomplete: str
) -> list[CompletionItem]:
    """Complete skill names for skill subcommands."""
    from ai_rules.skills import SkillManager

    config_dir = cli_facade.get_config_dir()
    manager = SkillManager(config_dir=config_dir, agent_id="")
    skills = manager.list_bundled_skills()
    return [
        CompletionItem(s.name, help=s.description[:60])
        for s in skills
        if s.name.startswith(incomplete)
    ]


@skill.command("list")
def skill_list() -> None:
    """List all bundled skills."""
    from rich.console import Console
    from rich.table import Table

    from ai_rules.skills import SkillManager

    console = Console()
    config_dir = cli_facade.get_config_dir()
    manager = SkillManager(config_dir=config_dir, agent_id="")
    skills = manager.list_bundled_skills()

    table = Table(title="Bundled Skills", show_header=True)
    table.add_column("Name", style="cyan")
    table.add_column("Description")

    for s in skills:
        table.add_row(s.name, s.description)

    console.print(table)


@skill.command("show")
@click.argument("name", shell_complete=complete_skills)
@click.option("--url", is_flag=True, help="Print the GitHub URL instead of content")
@click.option("--raw", is_flag=True, help="Print raw markdown without formatting")
def skill_show(name: str, url: bool, raw: bool) -> None:
    """Show a bundled skill's content.

    NAME is the skill directory name (e.g., research, code-reviewer).

    Examples:
        ai-agent-rules skill show research
        ai-agent-rules skill show research --url
        ai-agent-rules skill show code-reviewer --raw
    """
    from rich.console import Console
    from rich.markdown import Markdown

    from ai_rules.skills import SkillManager

    console = Console()
    config_dir = cli_facade.get_config_dir()
    manager = SkillManager(config_dir=config_dir, agent_id="")

    if url:
        managed = manager._get_managed_skills()
        if name not in managed:
            available = ", ".join(sorted(managed.keys()))
            console.print(
                f"[red]Error:[/red] Unknown skill '{name}'. Available: {available}"
            )
            sys.exit(1)
        skill_url = SkillManager.get_skill_url(name)
        if skill_url is None:
            console.print(
                "[red]Error:[/red] Could not determine GitHub URL. "
                "Package metadata may be unavailable."
            )
            sys.exit(1)
        click.echo(skill_url)
        return

    content = manager.get_skill_content(name)
    if content is None:
        managed = manager._get_managed_skills()
        available = ", ".join(sorted(managed.keys()))
        console.print(
            f"[red]Error:[/red] Unknown skill '{name}'. Available: {available}"
        )
        sys.exit(1)

    if raw:
        click.echo(content)
    else:
        console.print(Markdown(content))
