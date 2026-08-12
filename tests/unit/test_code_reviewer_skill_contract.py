"""Prompt-contract guards for the code-reviewer skill's boundary-review doctrine.

These assert structural invariants of the skill text itself — the 13 CI checks
verify none of them, yet a silent edit that drops the mutation protocol from the
Phase 2B Functionality briefing would reopen the #3398 class of miss. Each test
reads the bundled skill files as they ship, not a fixture.
"""

from __future__ import annotations

from importlib.resources import files as resource_files
from pathlib import Path

import pytest

SKILL_DIR = "skills/code-reviewer"


@pytest.fixture(scope="module")
def skill_md() -> str:
    root = Path(str(resource_files("ai_rules") / "config"))
    return (root / SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def template_md() -> str:
    root = Path(str(resource_files("ai_rules") / "config"))
    return (root / SKILL_DIR / "references" / "subagent-template.md").read_text(
        encoding="utf-8"
    )


def _section(text: str, header: str) -> str:
    """Return the body of a `### <header>` section up to the next `### ` header."""
    lines = text.splitlines()
    start = next(
        (i for i, ln in enumerate(lines) if ln.strip() == f"### {header}"), None
    )
    assert start is not None, f"section '### {header}' not found"
    end = next(
        (i for i in range(start + 1, len(lines)) if lines[i].startswith("### ")),
        len(lines),
    )
    return "\n".join(lines[start:end])


@pytest.mark.unit
class TestCodeReviewerSkillContract:
    def test_phase2b_functionality_briefing_carries_mutation_instruction(
        self, template_md: str
    ) -> None:
        """The Phase 2B Functionality specialist must own the executed mutation check.

        Boundary diffs route to Phase 2B, whose Functionality briefing comes from
        this section; if the mutation protocol is not here — or its direction is
        inverted — the one deterministic #3398 catch is lost. Assertions anchor on
        semantic invariants, not capitalization, so benign rewording survives while
        a reversed revert-direction trips.
        """
        section = _section(template_md, "Functionality & Testing Agent").lower()

        # Ownership + execution: the specialist runs the check, never merely reads it.
        assert "mutation check" in section
        assert "execute" in section
        assert "you own this" in section

        # Direction is load-bearing: revert PRODUCTION code, keep the added tests.
        # An inversion to "revert only the test hunks" must trip the negative check.
        assert "revert only the production" in section
        assert "keep the added tests" in section
        assert "revert only the test" not in section

        # Diff-verify the mutated tree before running the suite.
        assert "git diff" in section
        assert "confirm" in section

        # Run the project's full suite via its own tooling, not an ad-hoc subset.
        assert "full suite" in section
        assert "tooling" in section

        # Removing the fix must make the suite fail; staying green is a blocking miss.
        # No capitalization-pinned "RED" — a reword to "fails" stays valid.
        assert "stays green" in section
        assert "blocking" in section

        # Clean up the scratch worktree; inability to run is reported upward, never skipped.
        assert "remove the scratch worktree" in section
        assert "cannot execute" in section
        assert "precondition" in section

    def test_mutation_protocol_has_single_authoritative_home(
        self, skill_md: str, template_md: str
    ) -> None:
        """Exactly one authoritative definition; SKILL.md references it, not a copy."""
        assert template_md.count("authoritative mutation protocol") == 1
        assert "mutation protocol defined in" in skill_md
        assert "references/subagent-template.md" in skill_md
        # The step-by-step recipe lives only in the template, never duplicated.
        assert "Remove the scratch worktree when done" in template_md
        assert "Remove the scratch worktree when done" not in skill_md

    def test_boundary_diffs_route_to_orchestrated_path(self, skill_md: str) -> None:
        """A boundary_relevant diff must be forced into Phase 2B regardless of size."""
        assert "boundary_relevant" in skill_md
        assert (
            "routes to Phase 2B orchestrated review regardless of line/file count"
            in skill_md
        )
        # Phase 2A must be scoped to non-boundary diffs so no dead inline fallback remains.
        assert "Non-Boundary Small Diffs" in skill_md
        assert "somehow stays inline" not in skill_md

    def test_verdict_is_ordered_and_blocker_wins(self, skill_md: str) -> None:
        """The verdict must be an ordered tree where a verified blocker is never capped."""
        assert "never suppressed by the Comment cap" in skill_md
        # Applicability is stated, so a boundary PR with no linked issue is satisfiable.
        assert "applies only when the PR has a linked issue" in skill_md
        assert "applies only to fix PRs" in skill_md
