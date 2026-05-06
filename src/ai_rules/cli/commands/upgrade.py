from __future__ import annotations

import sys

import click


@click.command()
@click.option("--check", is_flag=True, help="Check for updates without installing")
@click.option("--force", is_flag=True, help="Force reinstall even if up to date")
@click.option(
    "-y", "--yes", is_flag=True, help="Auto-confirm installation without prompting"
)
@click.option(
    "--skip-install",
    is_flag=True,
    help="Skip running 'install --rebuild-cache' after upgrade",
)
@click.option(
    "--only",
    type=click.Choice(["ai-agent-rules", "ai-rules", "statusline"]),
    help="Only upgrade specific tool",
)
def upgrade(
    check: bool, force: bool, yes: bool, skip_install: bool, only: str | None
) -> None:
    """Upgrade ai-agent-rules and related tools to the latest versions.

    Each tool upgrades from its configured install source (PyPI or GitHub).

    Examples:
        ai-agent-rules upgrade                    # Check and install all updates
        ai-agent-rules upgrade --check            # Only check for updates
        ai-agent-rules upgrade -y                 # Auto-confirm installation
        ai-agent-rules upgrade --only=statusline  # Only upgrade statusline tool
    """
    from rich.console import Console
    from rich.prompt import Confirm

    from ai_rules.bootstrap import (
        ToolSource,
        check_tool_updates,
        get_effective_install_source,
        get_updatable_tools,
        perform_tool_upgrade,
    )
    from ai_rules.bootstrap.installer import install_tool
    from ai_rules.bootstrap.updater import _TOOL_ID_ALIASES

    console = Console()

    resolved_only = _TOOL_ID_ALIASES.get(only, only) if only else None
    all_tools = [
        t
        for t in get_updatable_tools()
        if resolved_only is None or t.tool_id == resolved_only
    ]
    tools = [t for t in all_tools if t.is_installed()]
    missing_tools = [t for t in all_tools if not t.is_installed()]

    for tool in missing_tools:
        console.print(f"[yellow]⚠[/yellow] {tool.display_name} is not installed")

    if missing_tools and not check:
        if yes or Confirm.ask("\nReinstall missing tools?", default=True):
            for tool in missing_tools:
                source, local_path = get_effective_install_source(tool.tool_id)
                from_github = source == ToolSource.GITHUB
                github_url = tool.github_install_url if from_github else None
                with console.status(f"Installing {tool.display_name}..."):
                    success, msg = install_tool(
                        tool.package_name,
                        from_github=from_github,
                        github_url=github_url,
                        local_path=local_path,
                    )
                if success:
                    console.print(f"[green]✓[/green] {tool.display_name} reinstalled")
                    tools.append(tool)
                else:
                    console.print(
                        f"[red]Error:[/red] Failed to install {tool.display_name}: {msg}"
                    )

    if not tools:
        if only:
            console.print(f"[yellow]⚠[/yellow] Tool '{only}' is not installed")
        else:
            console.print("[yellow]⚠[/yellow] No tools are installed")
        sys.exit(1)

    tool_updates = []
    for tool in tools:
        try:
            current = tool.get_version()
            if current:
                console.print(
                    f"[dim]{tool.display_name} current version: {current}[/dim]"
                )
        except Exception as e:
            console.print(
                f"[red]Error:[/red] Could not get {tool.display_name} version: {e}"
            )
            continue

        with console.status(f"Checking {tool.display_name} for updates..."):
            try:
                update_info = check_tool_updates(tool)
            except Exception as e:
                console.print(
                    f"[red]Error:[/red] Failed to check {tool.display_name} updates: {e}"
                )
                continue

        if update_info and (update_info.has_update or force):
            tool_updates.append((tool, update_info))
        elif update_info and not update_info.has_update:
            console.print(
                f"[green]✓[/green] {tool.display_name} is already up to date!"
            )

    console.print()

    if not tool_updates and not force:
        console.print("[green]✓[/green] All tools are up to date!")
        return

    for tool, update_info in tool_updates:
        if update_info.has_update:
            console.print(
                f"[cyan]Update available for {tool.display_name}:[/cyan] "
                f"{update_info.current_version} → {update_info.latest_version}"
            )

            if update_info.changelog_entries:
                console.print()
                for version, notes in update_info.changelog_entries:
                    console.print(f"  [bold]v{version}[/bold]")
                    for line in notes.strip().split("\n"):
                        if line.strip():
                            console.print(f"    {line.strip()}")
                console.print()

    if check:
        if tool_updates:
            console.print("\nRun [bold]ai-agent-rules upgrade[/bold] to install")
        return

    if not force and not yes:
        if len(tool_updates) == 1:
            prompt = f"\nInstall {tool_updates[0][0].display_name} update?"
        else:
            prompt = f"\nInstall {len(tool_updates)} updates?"
        if not Confirm.ask(prompt, default=True):
            console.print("[yellow]Cancelled.[/yellow]")
            return

    ai_rules_upgraded = False
    for tool, update_info in tool_updates:
        with console.status(f"Upgrading {tool.display_name}..."):
            try:
                success, msg, was_upgraded = perform_tool_upgrade(tool)
            except Exception as e:
                console.print(
                    f"\n[red]Error:[/red] {tool.display_name} upgrade failed: {e}"
                )
                continue

        if success:
            new_version = tool.get_version()
            if new_version == update_info.latest_version:
                console.print(
                    f"[green]✓[/green] {tool.display_name} upgraded to {new_version}"
                )
                if tool.tool_id == "ai-agent-rules":
                    ai_rules_upgraded = True
            elif new_version == update_info.current_version:
                console.print(
                    f"[yellow]⚠[/yellow] {tool.display_name} upgrade reported success but version unchanged ({new_version})"
                )
            else:
                console.print(
                    f"[green]✓[/green] {tool.display_name} upgraded to {new_version}"
                )
                if tool.tool_id == "ai-agent-rules":
                    ai_rules_upgraded = True
        else:
            console.print(
                f"[red]Error:[/red] {tool.display_name} upgrade failed: {msg}"
            )

    if ai_rules_upgraded and not skip_install:
        try:
            import subprocess

            console.print(
                "\n[dim]Running 'ai-agent-rules install --rebuild-cache'...[/dim]"
            )

            from ai_rules.state import get_active_profile

            current_profile = get_active_profile() or "default"

            result = subprocess.run(
                [
                    "ai-agent-rules",
                    "install",
                    "--rebuild-cache",
                    "-y",
                    "--profile",
                    current_profile,
                ],
                capture_output=False,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                console.print("[dim]✓ Install completed successfully[/dim]")
            else:
                console.print(
                    f"[yellow]⚠[/yellow] Install failed with exit code {result.returncode}"
                )
                console.print(
                    "[dim]Run 'ai-agent-rules install --rebuild-cache' manually to retry[/dim]"
                )
        except subprocess.TimeoutExpired:
            console.print("[yellow]⚠[/yellow] Install timed out after 30 seconds")
            console.print(
                "[dim]Run 'ai-agent-rules install --rebuild-cache' manually to retry[/dim]"
            )
        except Exception as e:
            console.print(f"[yellow]⚠[/yellow] Could not run install: {e}")
            console.print(
                "[dim]Run 'ai-agent-rules install --rebuild-cache' manually[/dim]"
            )
