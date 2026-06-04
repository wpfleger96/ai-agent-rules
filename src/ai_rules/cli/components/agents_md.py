"""AGENTS.md cache lifecycle component."""

from __future__ import annotations

from ai_rules.cli.context import (
    AgentsMdPlan,
    CliContext,
    Component,
    ComponentPlan,
    ComponentResult,
)


class AgentsMdComponent(Component):
    label = "AGENTS.md Cache"
    component_id = "agents-md"

    def plan(self, ctx: CliContext) -> AgentsMdPlan:
        from ai_rules.agents.shared import SharedAgent

        shared = next(
            (t for t in ctx.selected_targets if isinstance(t, SharedAgent)), None
        )
        if shared is None:
            return AgentsMdPlan()

        needs_rebuild = shared.needs_agents_md_cache and (
            ctx.rebuild_cache or shared.is_agents_md_cache_stale()
        )
        return AgentsMdPlan(has_changes=needs_rebuild, needs_rebuild=needs_rebuild)

    def apply(self, ctx: CliContext, plan: ComponentPlan) -> ComponentResult:
        if not isinstance(plan, AgentsMdPlan):
            return ComponentResult()

        if not plan.needs_rebuild or ctx.dry_run:
            return ComponentResult()

        from ai_rules.agents.shared import SharedAgent

        shared = next(
            (t for t in ctx.selected_targets if isinstance(t, SharedAgent)), None
        )
        if shared is None:
            return ComponentResult()

        shared.build_merged_agents_md(force_rebuild=ctx.rebuild_cache)
        return ComponentResult(changed=True, counts={"cache_updated": 1})

    def install(self, ctx: CliContext) -> ComponentResult:
        if ctx.dry_run:
            return ComponentResult()

        from ai_rules.agents.shared import SharedAgent

        shared = next(
            (t for t in ctx.selected_targets if isinstance(t, SharedAgent)), None
        )
        if shared is None or not shared.needs_agents_md_cache:
            return ComponentResult()

        shared.build_merged_agents_md(force_rebuild=ctx.rebuild_cache)
        return ComponentResult(changed=True, counts={"cache_updated": 1})

    def status(self, ctx: CliContext) -> ComponentResult:
        from ai_rules.agents.shared import SharedAgent

        shared = next(
            (t for t in ctx.selected_targets if isinstance(t, SharedAgent)), None
        )
        if shared is None or not shared.needs_agents_md_cache:
            return ComponentResult()

        if not shared.is_agents_md_cache_stale():
            return ComponentResult()

        from ai_rules.cli.display import print_warning
        from ai_rules.cli.runner import get_console

        console = get_console(ctx)
        console.print("[bold]AGENTS.md Cache[/bold]")
        print_warning("Cached AGENTS.md is stale", indent=2)

        cache_path = shared.agents_md_cache_path
        if cache_path and cache_path.exists():
            current_text = cache_path.read_text(encoding="utf-8")
            from_label = "Cached (current)"
        else:
            base_path = shared.config_dir / "AGENTS.md"
            current_text = (
                base_path.read_text(encoding="utf-8") if base_path.exists() else ""
            )
            from_label = "Base (current)"

        expected_text = shared.get_expected_agents_md_content()

        from ai_rules.symlinks import format_unified_diff

        diff_output = format_unified_diff(
            current_text.splitlines(keepends=True),
            expected_text.splitlines(keepends=True),
            from_label,
            "Expected (merged)",
        )
        if diff_output:
            console.print(diff_output)

        console.print()

        return ComponentResult(ok=False, changed=True, counts={"cache_stale": 1})

    def diff(self, ctx: CliContext) -> ComponentResult:
        return self.status(ctx)

    def uninstall(self, ctx: CliContext) -> ComponentResult:
        from ai_rules.config import Config

        cache_path = Config.get_cache_dir() / "shared" / "AGENTS.md"

        if ctx.dry_run:
            if cache_path.exists():
                from ai_rules.cli.display import print_dim

                print_dim(f"Would remove AGENTS.md cache: {cache_path}", indent=2)
                return ComponentResult(changed=True)
            return ComponentResult()

        if not cache_path.exists():
            return ComponentResult()

        from ai_rules.cli.display import print_success

        cache_path.unlink()
        print_success("Removed AGENTS.md cache", indent=2)
        return ComponentResult(changed=True, counts={"removed": 1})
