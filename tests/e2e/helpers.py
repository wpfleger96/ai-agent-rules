import json
import os
import re
import subprocess
import sys

from collections.abc import Callable
from pathlib import Path

CliResult = subprocess.CompletedProcess[str]
CliRunner = Callable[..., CliResult]


def is_windows() -> bool:
    return sys.platform == "win32"


def strip_ansi(text: str) -> str:
    ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
    return ansi_escape.sub("", text)


# ---------------------------------------------------------------------------
# Isolated-home subprocess harness
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).parents[2]
SRC_PATH = REPO_ROOT / "src"

# Core symlink/merge components. These exercise exactly the machinery that the
# install pipeline materializes on disk (settings cache, AGENTS.md merge, the
# per-agent symlink builders, the MCP managers, Claude extensions, skills) while
# excluding the components that reach for external CLIs/network (optional tool
# bootstrap via `uv`, Claude plugin/marketplace sync via the `claude` CLI, and
# shell-completion installation). Scoping to these keeps E2E hermetic and
# deterministic across the CI matrix.
CORE_COMPONENTS = "settings,agents-md,config,mcps,skills,extensions"


def make_home_env(home_dir: Path, *, columns: int | None = None) -> dict[str, str]:
    """Build environment overrides that isolate a CLI run inside ``home_dir``.

    Everything the app touches (HOME, the state/cache dir at ~/.ai-agent-rules,
    XDG dirs, the user config file) is rooted under ``home_dir`` so runs never
    read or mutate the developer's real configuration.
    """
    env: dict[str, str] = {
        "HOME": str(home_dir),
        "USERPROFILE": str(home_dir),
        "APPDATA": str(home_dir / "AppData" / "Roaming"),
        "LOCALAPPDATA": str(home_dir / "AppData" / "Local"),
        "NO_COLOR": "1",
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUTF8": "1",
        "XDG_CACHE_HOME": str(home_dir / ".cache"),
        "XDG_DATA_HOME": str(home_dir / ".local" / "share"),
        "XDG_CONFIG_HOME": str(home_dir / ".config"),
        "PATH": os.environ.get("PATH", ""),
        "SHELL": "/bin/bash",
    }
    if columns is not None:
        env["COLUMNS"] = str(columns)
    return env


def make_cli_runner(home_dir: Path, env_overrides: dict[str, str]) -> CliRunner:
    """Return a ``run(args)`` callable that invokes the real CLI in a subprocess.

    Running the installed module via ``python -m ai_rules.cli`` (rather than the
    in-process Click runner) is what makes these tests end-to-end: argument
    parsing, the component runner's thread pool, atomic writes, and the
    subprocess process boundary are all exercised exactly as in production.
    """

    def _run(
        args: list[str],
        extra_env: dict[str, str] | None = None,
        timeout: int = 60,
    ) -> CliResult:
        base_env = {**os.environ, **env_overrides}
        existing = base_env.get("PYTHONPATH", "")
        base_env["PYTHONPATH"] = (
            str(SRC_PATH)
            if not existing
            else os.pathsep.join([str(SRC_PATH), existing])
        )
        if extra_env:
            base_env.update(extra_env)
        return subprocess.run(
            [sys.executable, "-m", "ai_rules.cli", *args],
            capture_output=True,
            encoding="utf-8",
            check=False,
            cwd=REPO_ROOT,
            env=base_env,
            timeout=timeout,
        )

    return _run


# ---------------------------------------------------------------------------
# Toy config-dir builder
# ---------------------------------------------------------------------------


def build_config_dir(
    config_dir: Path,
    *,
    with_extensions: bool = True,
    with_skills: bool = True,
    mcps: dict | None = None,
    claude_settings: dict | None = None,
) -> Path:
    """Create a realistic standalone config dir for ``install --config-dir``.

    Mirrors the on-disk shape a user keeps in their own rules repo: a shared
    AGENTS.md, per-agent instruction + settings files, optional Claude
    agents/commands, bundled skills, and an optional shared ``mcps.json``.
    """
    config_dir.mkdir(parents=True, exist_ok=True)

    (config_dir / "AGENTS.md").write_text("# Shared Agent Rules\n", encoding="utf-8")

    claude_dir = config_dir / "claude"
    claude_dir.mkdir(exist_ok=True)
    (claude_dir / "CLAUDE.md").write_text(
        "# Claude rules\n@~/AGENTS.md\n", encoding="utf-8"
    )
    settings = claude_settings if claude_settings is not None else {"theme": "dark"}
    (claude_dir / "settings.json").write_text(json.dumps(settings), encoding="utf-8")

    if with_extensions:
        agents_dir = claude_dir / "agents"
        agents_dir.mkdir(exist_ok=True)
        (agents_dir / "demo-agent.md").write_text("# Demo Agent\n", encoding="utf-8")
        commands_dir = claude_dir / "commands"
        commands_dir.mkdir(exist_ok=True)
        (commands_dir / "hello.md").write_text("# Hello Command\n", encoding="utf-8")

    codex_dir = config_dir / "codex"
    codex_dir.mkdir(exist_ok=True)
    (codex_dir / "config.toml").write_text('model = "test-model"\n', encoding="utf-8")
    (codex_dir / "AGENTS.md").write_text("@~/AGENTS.md\n", encoding="utf-8")

    gemini_dir = config_dir / "gemini"
    gemini_dir.mkdir(exist_ok=True)
    (gemini_dir / "GEMINI.md").write_text("# Gemini rules\n", encoding="utf-8")
    (gemini_dir / "settings.json").write_text('{"name": "gemini"}', encoding="utf-8")

    amp_dir = config_dir / "amp"
    amp_dir.mkdir(exist_ok=True)
    (amp_dir / "AGENTS.md").write_text("# Amp rules\n", encoding="utf-8")
    (amp_dir / "settings.json").write_text('{"amp.showCosts": true}', encoding="utf-8")

    goose_dir = config_dir / "goose"
    goose_dir.mkdir(exist_ok=True)
    (goose_dir / "config.yaml").write_text("test: e2e\n", encoding="utf-8")
    (goose_dir / ".goosehints").write_text("# Goose hints\n", encoding="utf-8")

    if with_skills:
        skill_dir = config_dir / "skills" / "demo-skill"
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text(
            "---\nname: demo-skill\ndescription: A demo skill\n---\n# Demo\n",
            encoding="utf-8",
        )

    if mcps is not None:
        (config_dir / "mcps.json").write_text(json.dumps(mcps), encoding="utf-8")

    return config_dir


# ---------------------------------------------------------------------------
# Filesystem inspection helpers
# ---------------------------------------------------------------------------

CACHE_MARKER = ".ai-agent-rules/cache"


def collect_symlink_manifest(home_dir: Path) -> list[str]:
    """Return a sorted, path-normalized manifest of every symlink under ``home``.

    Each entry is ``<target-relative-to-home> -> <source-kind>`` where the kind
    is ``cache`` when the link resolves into the merged-settings cache and
    ``source`` otherwise. This is the CI-enforceable encoding of the
    "symlink list matches a pre-refactor snapshot" guarantee: the *set* and
    *kind* of links install produces is pinned, while volatile absolute paths
    are abstracted away.
    """
    manifest = []
    for path in home_dir.rglob("*"):
        if not path.is_symlink():
            continue
        rel = path.relative_to(home_dir).as_posix()
        raw_target = os.readlink(path)
        kind = "cache" if CACHE_MARKER in raw_target.replace(os.sep, "/") else "source"
        manifest.append(f"{rel} -> {kind}")
    return sorted(manifest)


def read_symlink_content(path: Path) -> str:
    """Read text through a symlink (resolving to its real source/cache file)."""
    return path.read_text(encoding="utf-8")


def find_backups(directory: Path) -> list[Path]:
    """Return any ai-agent-rules backup files created under ``directory``."""
    return sorted(directory.rglob("*.ai-agent-rules-backup.*"))


def normalize_output(text: str, replacements: dict[str, str]) -> str:
    """Normalize CLI output for golden comparison.

    Strips ANSI, applies longest-first path → placeholder substitutions, and
    trims trailing whitespace per line so wrapping/indent jitter does not break
    the golden.
    """
    out = strip_ansi(text)
    for needle in sorted(replacements, key=len, reverse=True):
        out = out.replace(needle, replacements[needle])
    lines = [line.rstrip() for line in out.splitlines()]
    return "\n".join(lines).strip() + "\n"
