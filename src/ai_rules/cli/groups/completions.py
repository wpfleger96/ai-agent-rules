from __future__ import annotations

import sys

import click


@click.group()
def completions() -> None:
    """Manage shell tab completion."""
    pass


from ai_rules.completions import get_supported_shells

_SUPPORTED_SHELLS = list(get_supported_shells())


@completions.command(name="bash")
def completions_bash() -> None:
    """Output bash completion script for manual installation."""
    from ai_rules.cli.display import console
    from ai_rules.completions import generate_completion_script

    try:
        script = generate_completion_script("bash")
        console.print(script)
        console.print(
            "\n[dim]To install: Add the above to your ~/.bashrc or run:[/dim]"
        )
        console.print("[dim]  ai-agent-rules completions install[/dim]")
    except Exception as e:
        from ai_rules.cli.display import print_error

        print_error(f"Error generating completion script: {e}")
        sys.exit(1)


@completions.command(name="zsh")
def completions_zsh() -> None:
    """Output zsh completion script for manual installation."""
    from ai_rules.cli.display import console
    from ai_rules.completions import generate_completion_script

    try:
        script = generate_completion_script("zsh")
        console.print(script)
        console.print("\n[dim]To install: Add the above to your ~/.zshrc or run:[/dim]")
        console.print("[dim]  ai-agent-rules completions install[/dim]")
    except Exception as e:
        from ai_rules.cli.display import print_error

        print_error(f"Error generating completion script: {e}")
        sys.exit(1)


@completions.command(name="install")
@click.option(
    "--shell",
    type=click.Choice(_SUPPORTED_SHELLS, case_sensitive=False),
    help="Shell type (auto-detected if not specified)",
)
def completions_install(shell: str | None) -> None:
    """Install shell completion to config file."""
    from ai_rules.cli.display import console, print_error
    from ai_rules.completions import detect_shell, install_completion

    if shell is None:
        shell = detect_shell()
        if shell is None:
            print_error("Could not detect shell. Please specify with --shell")
            sys.exit(1)
        console.print(f"[dim]Detected shell:[/dim] {shell}")

    success, message = install_completion(shell, dry_run=False)

    if success:
        console.print(f"[green]✓[/green] {message}")
    else:
        print_error(message)
        sys.exit(1)


@completions.command(name="uninstall")
@click.option(
    "--shell",
    type=click.Choice(_SUPPORTED_SHELLS, case_sensitive=False),
    help="Shell type (auto-detected if not specified)",
)
def completions_uninstall(shell: str | None) -> None:
    """Remove shell completion from config file."""
    from ai_rules.cli.display import console, print_error
    from ai_rules.completions import (
        detect_shell,
        find_config_file,
        uninstall_completion,
    )

    if shell is None:
        shell = detect_shell()
        if shell is None:
            print_error("Could not detect shell. Please specify with --shell")
            sys.exit(1)

    config_path = find_config_file(shell)
    if config_path is None:
        print_error(f"No {shell} config file found")
        sys.exit(1)

    success, message = uninstall_completion(config_path)

    if success:
        console.print(f"[green]✓[/green] {message}")
    else:
        print_error(message)
        sys.exit(1)


@completions.command(name="update")
@click.option(
    "--shell",
    type=click.Choice(_SUPPORTED_SHELLS, case_sensitive=False),
    help="Shell type (auto-detected if not specified)",
)
def completions_update(shell: str | None) -> None:
    """Re-generate completion block (fixes PATH shadowing issues)."""
    from ai_rules.cli.display import console, print_error
    from ai_rules.completions import detect_shell, update_completion

    if shell is None:
        shell = detect_shell()
        if shell is None:
            print_error("Could not detect shell. Use --shell to specify.")
            sys.exit(1)
        console.print(f"[dim]Detected shell:[/dim] {shell}")

    success, message = update_completion(shell, dry_run=False)

    if success:
        console.print(f"[green]✓[/green] {message}")
    else:
        print_error(message)
        sys.exit(1)


@completions.command(name="status")
def completions_status() -> None:
    """Show shell completion installation status."""
    from rich.table import Table

    from ai_rules.cli.display import console, print_warning
    from ai_rules.completions import (
        detect_shell,
        find_config_file,
        is_completion_installed,
    )

    detected_shell = detect_shell()
    console.print("[bold cyan]Shell Completions Status[/bold cyan]\n")

    if detected_shell:
        console.print(f"Detected shell: [cyan]{detected_shell}[/cyan]\n")
    else:
        print_warning("No supported shell detected")

    table = Table(show_header=True)
    table.add_column("Shell")
    table.add_column("Status")
    table.add_column("Config File")

    for shell in get_supported_shells():
        config_path = find_config_file(shell)

        if config_path is None:
            status = "[dim]-[/dim]"
            config_str = "[dim]No config file found[/dim]"
        elif is_completion_installed(config_path):
            status = "[green]✓[/green]"
            config_str = str(config_path)
        else:
            status = "[yellow]○[/yellow]"
            config_str = f"{config_path} [dim](not installed)[/dim]"

        shell_name = f"[bold]{shell}[/bold]" if shell == detected_shell else shell
        table.add_row(shell_name, status, config_str)

    console.print(table)
    console.print("\n[dim]To install: ai-agent-rules completions install[/dim]")
