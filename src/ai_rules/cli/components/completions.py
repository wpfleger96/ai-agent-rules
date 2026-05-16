"""Shell completion lifecycle component."""

from __future__ import annotations

from ai_rules.cli.context import (
    CliContext,
    CompletionsPlan,
    Component,
    ComponentPlan,
    ComponentResult,
)


class CompletionsComponent(Component):
    label = "Shell Completions"
    display_name = "Shell Completions"
    component_id = "completions"

    def plan(self, ctx: CliContext) -> CompletionsPlan:
        if ctx.skip_completions:
            return CompletionsPlan(has_changes=False)

        from ai_rules.completions import detect_shell

        shell = detect_shell()
        if not shell:
            return CompletionsPlan(has_changes=False)

        return CompletionsPlan(has_changes=True, shell=shell, needs_install=True)

    def apply(self, ctx: CliContext, plan: ComponentPlan) -> ComponentResult:
        if not isinstance(plan, CompletionsPlan):
            return ComponentResult()

        from ai_rules.cli.display import print_done
        from ai_rules.cli.runner import get_console

        if not plan.needs_install or plan.shell is None:
            return ComponentResult()

        from ai_rules.completions import install_completion

        console = get_console(ctx)
        success, msg = install_completion(plan.shell, dry_run=ctx.dry_run)
        if success and not ctx.dry_run and "already installed" not in msg:
            console.print()
            print_done(msg)

        return ComponentResult(changed=success)

    def install(self, ctx: CliContext) -> ComponentResult:
        if ctx.skip_completions:
            return ComponentResult()

        from ai_rules.completions import detect_shell, install_completion

        shell = detect_shell()
        if not shell:
            return ComponentResult()

        from ai_rules.cli.display import print_done

        success, msg = install_completion(shell, dry_run=ctx.dry_run)
        if success and not ctx.dry_run and "already installed" not in msg:
            ctx.console.print()
            print_done(msg)

        return ComponentResult(changed=success)

    def status(self, ctx: CliContext) -> ComponentResult:
        from ai_rules.cli.runner import get_console
        from ai_rules.completions import (
            detect_shell,
            find_config_file,
            get_supported_shells,
            is_completion_installed,
        )

        console = get_console(ctx)
        shell = detect_shell()
        if shell:
            config_path = find_config_file(shell)
            if config_path and is_completion_installed(config_path):
                console.print(
                    f"  [green]✓[/green] {shell} completion installed ({config_path})"
                )
            else:
                console.print(
                    f"  [yellow]○[/yellow] {shell} completion not installed "
                    "(run: ai-agent-rules completions install)"
                )
        else:
            supported = ", ".join(get_supported_shells())
            console.print(
                f"  [dim]Shell completion not available for your shell (only {supported} supported)[/dim]"
            )

        console.print()
        return ComponentResult()
