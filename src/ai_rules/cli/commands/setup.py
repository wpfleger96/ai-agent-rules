from __future__ import annotations

import click

import ai_rules.cli as cli_facade

from ai_rules.cli.commands.install import install


@click.command()
@click.option("--github", is_flag=True, help="Install from GitHub instead of PyPI")
@click.option("-y", "--yes", is_flag=True, help="Auto-confirm without prompting")
@click.option("--dry-run", is_flag=True, help="Show what would be done")
@click.option("--skip-symlinks", is_flag=True, help="Skip symlink installation step")
@click.option("--skip-completions", is_flag=True, help="Skip shell completion setup")
@click.option(
    "--profile",
    default=None,
    shell_complete=cli_facade.complete_profiles,
    help="Profile to use (default: 'default')",
)
@click.pass_context
def setup(
    ctx: click.Context,
    github: bool,
    yes: bool,
    dry_run: bool,
    skip_symlinks: bool,
    skip_completions: bool,
    profile: str | None,
) -> None:
    """One-time setup: install symlinks and make ai-agent-rules available system-wide.

    This is the recommended way to install ai-agent-rules for first-time users.

    Example:
        uvx ai-agent-rules setup
    """
    from rich.console import Console
    from rich.prompt import Confirm

    from ai_rules.bootstrap import (
        ToolSource,
        ensure_statusline_installed,
        get_effective_install_source,
        get_tool_config_dir,
        install_tool,
    )

    console = Console()
    from ai_rules.bootstrap.updater import (
        check_tool_updates,
        get_tool_by_id,
        perform_tool_upgrade,
    )

    console.print("[bold cyan]Step 1/3: Install ai-agent-rules system-wide[/bold cyan]")
    console.print("This allows you to run 'ai-agent-rules' from any directory.\n")

    statusline_source, statusline_local_path = get_effective_install_source(
        "statusline", cli_github_flag=github
    )
    statusline_result, statusline_message = ensure_statusline_installed(
        dry_run=dry_run,
        from_github=statusline_source == ToolSource.GITHUB,
        local_path=statusline_local_path,
        allow_source_switch=True,
    )
    if statusline_result == "installed":
        if dry_run and statusline_message:
            console.print(f"[dim]{statusline_message}[/dim]")
        else:
            console.print("[green]✓[/green] Installed claude-statusline")
    elif statusline_result == "upgraded":
        console.print(
            f"[green]✓[/green] Upgraded claude-statusline ({statusline_message})"
        )
    elif statusline_result == "upgrade_available":
        console.print(f"[dim]{statusline_message}[/dim]")
    elif statusline_result == "source_switched":
        console.print(
            f"[green]✓[/green] Switched claude-statusline source ({statusline_message})"
        )
    elif statusline_result == "source_switch_needed":
        if dry_run and statusline_message:
            console.print(f"[dim]{statusline_message}[/dim]")
    elif statusline_result == "failed":
        console.print(
            "[yellow]⚠[/yellow] Failed to install claude-statusline (continuing anyway)"
        )

    ai_rules_tool = get_tool_by_id("ai-agent-rules")
    tool_install_success = False

    if ai_rules_tool and ai_rules_tool.is_installed():
        from ai_rules.bootstrap import ToolSource, get_tool_source, uninstall_tool

        ai_rules_source, ai_rules_local_path = get_effective_install_source(
            "ai-agent-rules", cli_github_flag=github
        )
        ai_rules_from_github = ai_rules_source == ToolSource.GITHUB
        current_source = get_tool_source(ai_rules_tool.package_name)
        desired_source = ai_rules_source
        needs_source_switch = current_source != desired_source

        if needs_source_switch:
            if ai_rules_source == ToolSource.LOCAL:
                source_name = f"local ({ai_rules_local_path})"
            elif ai_rules_from_github:
                source_name = "GitHub"
            else:
                source_name = "PyPI"
            if dry_run:
                console.print(
                    f"[dim]Would switch ai-agent-rules from {current_source.name if current_source else 'unknown'} to {source_name}[/dim]"
                )
                tool_install_success = True
            else:
                if not yes and not Confirm.ask(
                    f"Switch ai-agent-rules to {source_name} install?", default=True
                ):
                    console.print("[yellow]Skipped source switch[/yellow]")
                    tool_install_success = True
                else:
                    uninstall_success, _ = uninstall_tool(ai_rules_tool.package_name)
                    if uninstall_success:
                        github_url = (
                            ai_rules_tool.github_install_url
                            if ai_rules_from_github
                            else None
                        )
                        success, message = install_tool(
                            ai_rules_tool.package_name,
                            from_github=ai_rules_from_github,
                            github_url=github_url,
                            local_path=ai_rules_local_path,
                            force=True,
                        )
                        if success:
                            console.print(
                                f"[green]✓[/green] Switched to {source_name} install"
                            )
                            tool_install_success = True
                        else:
                            console.print(
                                f"[red]Error:[/red] Failed to install: {message}"
                            )
                    else:
                        console.print(
                            "[red]Error:[/red] Failed to uninstall current version"
                        )
        else:
            try:
                update_info = check_tool_updates(ai_rules_tool, timeout=10)
                if update_info and update_info.has_update:
                    if dry_run:
                        console.print(
                            f"[dim]Would upgrade ai-agent-rules {update_info.current_version} → {update_info.latest_version}[/dim]"
                        )
                        tool_install_success = True
                    else:
                        if not yes and not Confirm.ask(
                            f"Upgrade ai-agent-rules {update_info.current_version} → {update_info.latest_version}?",
                            default=True,
                        ):
                            console.print(
                                "[yellow]Skipped ai-agent-rules upgrade[/yellow]"
                            )
                            tool_install_success = True
                        else:
                            success, msg, _ = perform_tool_upgrade(ai_rules_tool)
                            if success:
                                console.print(
                                    f"[green]✓[/green] Upgraded ai-agent-rules ({update_info.current_version} → {update_info.latest_version})"
                                )
                                tool_install_success = True
                            else:
                                console.print(
                                    "[red]Error:[/red] Failed to upgrade ai-agent-rules"
                                )
                else:
                    tool_install_success = True
            except Exception:
                pass

    if not tool_install_success:
        if not yes and not dry_run:
            if not Confirm.ask("Install ai-agent-rules permanently?", default=True):
                console.print(
                    "\n[yellow]Skipped.[/yellow] You can still run via: uvx ai-agent-rules <command>"
                )
                return

        try:
            ai_rules_source, ai_rules_local_path = get_effective_install_source(
                "ai-agent-rules", cli_github_flag=github
            )
            ai_rules_from_github = ai_rules_source == ToolSource.GITHUB
            ai_rules_tool_spec = get_tool_by_id("ai-agent-rules")
            github_url = (
                ai_rules_tool_spec.github_install_url
                if (ai_rules_from_github and ai_rules_tool_spec)
                else None
            )
            success, message = install_tool(
                "ai-agent-rules",
                from_github=ai_rules_from_github,
                github_url=github_url,
                local_path=ai_rules_local_path,
                force=yes,
                dry_run=dry_run,
            )

            if dry_run:
                console.print(f"[dim]{message}[/dim]")
                tool_install_success = True
            elif success:
                console.print("[green]✓[/green] Tool installed successfully")
                tool_install_success = True
            else:
                console.print(f"\n[red]Error:[/red] {message}")
                console.print("\n[yellow]Manual installation:[/yellow]")
                console.print("  uv tool install ai-agent-rules")
                return
        except Exception as e:
            console.print(f"\n[red]Error:[/red] {e}")
            return

    if not skip_symlinks:
        console.print(
            "[bold cyan]Step 2/3: Installing AI agent configuration symlinks[/bold cyan]\n"
        )

        config_dir_override = None
        if tool_install_success and not dry_run:
            try:
                tool_config_dir = get_tool_config_dir("ai-agent-rules")
                if tool_config_dir.exists():
                    config_dir_override = str(tool_config_dir)
                else:
                    console.print(
                        f"[yellow]Warning:[/yellow] Tool config not found at expected location: {tool_config_dir}"
                    )
                    console.print(
                        "[dim]Falling back to current config directory[/dim]\n"
                    )
            except Exception as e:
                console.print(
                    f"[yellow]Warning:[/yellow] Could not determine tool config path: {e}"
                )
                console.print("[dim]Falling back to current config directory[/dim]\n")

        ctx.invoke(
            install,
            yes=yes,
            dry_run=dry_run,
            rebuild_cache=False,
            agents=None,
            skip_completions=True,
            profile=profile,
            config_dir_override=config_dir_override,
        )

    if not skip_completions:
        from ai_rules.completions import (
            detect_shell,
            find_config_file,
            get_supported_shells,
            install_completion,
            is_completion_installed,
            is_legacy_completion_block,
            update_completion,
        )

        console.print("\n[bold cyan]Step 3/3: Shell completion setup[/bold cyan]\n")

        shell = detect_shell()
        if shell:
            config_path = find_config_file(shell)
            if config_path and is_completion_installed(config_path):
                if is_legacy_completion_block(config_path):
                    success, msg = update_completion(shell, dry_run=dry_run)
                    if success:
                        console.print(f"[green]✓[/green] {msg}")
                    else:
                        console.print(f"[yellow]⚠[/yellow] {msg}")
                else:
                    console.print(
                        f"[green]✓[/green] {shell} completion already installed"
                    )
            elif (
                yes
                or dry_run
                or Confirm.ask(f"Install {shell} tab completion?", default=True)
            ):
                success, msg = install_completion(shell, dry_run=dry_run)
                if success:
                    console.print(f"[green]✓[/green] {msg}")
                else:
                    console.print(f"[yellow]⚠[/yellow] {msg}")
        else:
            supported = ", ".join(get_supported_shells())
            console.print(
                f"[dim]Shell completion not available for your shell (only {supported} supported)[/dim]"
            )

    if dry_run:
        console.print("\n[dim]Dry run complete - no changes were made.[/dim]")
    else:
        console.print("\n[green]✓ Setup complete![/green]")
        console.print(
            "You can now run [bold]ai-agent-rules[/bold] (or [bold]ai-rules[/bold]) from anywhere."
        )
