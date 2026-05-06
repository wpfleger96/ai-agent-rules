from __future__ import annotations

import click

import ai_rules.cli as cli_facade


@click.command("list-agents")
def list_agents_cmd() -> None:
    """List available AI agents."""
    from rich.console import Console
    from rich.table import Table

    from ai_rules.config import Config
    from ai_rules.symlinks import check_symlink

    console = Console()

    config_dir = cli_facade.get_config_dir()
    config = Config.load()
    targets = cli_facade.get_targets(config_dir, config)

    table = Table(title="Available AI Agents", show_header=True)
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="bold")
    table.add_column("Symlinks", justify="right")
    table.add_column("Status")

    for target in targets:
        all_symlinks = target.symlinks
        filtered_symlinks = target.get_filtered_symlinks()
        excluded_count = len(all_symlinks) - len(filtered_symlinks)

        installed = 0
        for tgt, source in filtered_symlinks:
            status_code, _ = check_symlink(tgt, source)
            if status_code == "correct":
                installed += 1

        total = len(filtered_symlinks)
        status = f"{installed}/{total} installed"
        if excluded_count > 0:
            status += f" ({excluded_count} excluded)"

        table.add_row(target.target_id, target.name, str(total), status)

    console.print(table)
