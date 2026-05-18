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
@click.option(
    "--download-url",
    is_flag=True,
    help="Print browser download URL for all skills",
)
def skill_list(download_url: bool) -> None:
    """List all bundled skills."""
    from rich.table import Table

    from ai_rules.cli.display import console
    from ai_rules.skills import SkillManager

    if download_url:
        url = SkillManager.get_download_url()
        if url is None:
            from ai_rules.cli.display import print_error

            print_error(
                "Could not determine GitHub URL. Package metadata may be unavailable."
            )
            sys.exit(1)
        click.echo(url)
        return

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
@click.option(
    "--download-url",
    is_flag=True,
    help="Print browser download URL for this skill",
)
@click.option("--raw", is_flag=True, help="Print raw markdown without formatting")
def skill_show(name: str, url: bool, download_url: bool, raw: bool) -> None:
    """Show a bundled skill's content.

    NAME is the skill directory name (e.g., research, code-reviewer).

    Examples:
        ai-agent-rules skill show research
        ai-agent-rules skill show research --url
        ai-agent-rules skill show research --download-url
        ai-agent-rules skill show code-reviewer --raw
    """
    from rich.markdown import Markdown

    from ai_rules.cli.display import console, print_error
    from ai_rules.skills import SkillManager

    config_dir = cli_facade.get_config_dir()
    manager = SkillManager(config_dir=config_dir, agent_id="")

    if url and download_url:
        raise click.UsageError("--url and --download-url are mutually exclusive")
    if raw and (url or download_url):
        raise click.UsageError("--raw cannot be combined with --url or --download-url")

    if url or download_url:
        managed = manager._get_managed_skills()
        if name not in managed:
            available = ", ".join(sorted(managed.keys()))
            print_error(f"Unknown skill '{name}'. Available: {available}")
            sys.exit(1)

        if download_url:
            result = SkillManager.get_download_url(name)
        else:
            result = SkillManager.get_skill_url(name)

        if result is None:
            print_error(
                "Could not determine GitHub URL. Package metadata may be unavailable."
            )
            sys.exit(1)
        click.echo(result)
        return

    content = manager.get_skill_content(name)
    if content is None:
        managed = manager._get_managed_skills()
        available = ", ".join(sorted(managed.keys()))
        print_error(f"Unknown skill '{name}'. Available: {available}")
        sys.exit(1)

    if raw:
        click.echo(content)
    else:
        console.print(Markdown(content))
