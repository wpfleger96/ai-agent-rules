"""Shell completion lifecycle component."""

from __future__ import annotations

from ai_rules.cli.context import CliContext, Component, ComponentResult


class CompletionsComponent(Component):
    label = "Shell Completions"

    def install(self, ctx: CliContext) -> ComponentResult:
        if ctx.skip_completions:
            return ComponentResult()

        from ai_rules.completions import detect_shell, install_completion

        shell = detect_shell()
        if not shell:
            return ComponentResult()

        success, msg = install_completion(shell, dry_run=ctx.dry_run)
        if success and not ctx.dry_run and "already installed" not in msg:
            ctx.console.print(f"\n[dim]✓ {msg}[/dim]")

        return ComponentResult(changed=success)

    def status(self, ctx: CliContext) -> ComponentResult:
        from ai_rules.completions import (
            detect_shell,
            find_config_file,
            get_supported_shells,
            is_completion_installed,
        )

        ctx.console.print("[bold cyan]Shell Completions[/bold cyan]\n")

        shell = detect_shell()
        if shell:
            config_path = find_config_file(shell)
            if config_path and is_completion_installed(config_path):
                ctx.console.print(
                    f"  [green]✓[/green] {shell} completion installed ({config_path})"
                )
            else:
                ctx.console.print(
                    f"  [yellow]○[/yellow] {shell} completion not installed "
                    "(run: ai-agent-rules completions install)"
                )
        else:
            supported = ", ".join(get_supported_shells())
            ctx.console.print(
                f"  [dim]Shell completion not available for your shell (only {supported} supported)[/dim]"
            )

        ctx.console.print()
        return ComponentResult()
