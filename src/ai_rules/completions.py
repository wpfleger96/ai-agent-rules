"""Shell completion installation and management."""

import os
import re

from dataclasses import dataclass
from pathlib import Path

COMPLETION_MARKER_START = "# ai-agent-rules shell completion"
COMPLETION_MARKER_END = "# End ai-agent-rules shell completion"

_LEGACY_MARKER_START = "# ai-rules shell completion"
_LEGACY_MARKER_END = "# End ai-rules shell completion"

CANONICAL_CMD = "ai-agent-rules"
ALIAS_CMD = "ai-rules"


@dataclass
class ShellConfig:
    """Configuration for a supported shell."""

    name: str
    config_files: list[str]  # Relative to home, in priority order

    def get_config_candidates(self) -> list[Path]:
        """Get existing config file paths for this shell."""
        home = Path.home()
        return [home / cf for cf in self.config_files if (home / cf).exists()]


@dataclass
class PowerShellConfig(ShellConfig):
    def get_config_candidates(self) -> list[Path]:
        profile = _get_powershell_profile_path()
        if profile and profile.exists():
            return [profile]
        return []


def _get_powershell_profile_path() -> Path | None:
    import subprocess

    for exe in ("pwsh", "powershell"):
        try:
            result = subprocess.run(
                [exe, "-NoProfile", "-Command", "Write-Output $PROFILE"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                return Path(result.stdout.strip())
        except FileNotFoundError, subprocess.TimeoutExpired:
            continue
    return None


SHELL_REGISTRY: dict[str, ShellConfig] = {
    "bash": ShellConfig("bash", [".bashrc", ".bash_profile", ".profile"]),
    "zsh": ShellConfig("zsh", [".zshrc", ".zprofile"]),
    "powershell": PowerShellConfig("powershell", []),
}


def get_supported_shells() -> tuple[str, ...]:
    """Get tuple of supported shell names."""
    return tuple(SHELL_REGISTRY.keys())


def detect_shell() -> str | None:
    """Detect current shell from $SHELL environment variable.

    Returns:
        Shell name if supported, None otherwise
    """
    try:
        import shellingham

        name, _ = shellingham.detect_shell()
        if name in ("pwsh", "powershell"):
            return "powershell"
        return name if name in SHELL_REGISTRY else None
    except Exception:
        shell_path = os.environ.get("SHELL", "")
        name = Path(shell_path).name if shell_path else None
        return name if name in SHELL_REGISTRY else None


def get_shell_config_candidates(shell: str) -> list[Path]:
    """Return candidate config files for a shell, checking which exist.

    Args:
        shell: Shell name (e.g., 'bash', 'zsh')

    Returns:
        List of config file paths that exist on the system
    """
    shell_config = SHELL_REGISTRY.get(shell)
    if shell_config is None:
        return []
    return shell_config.get_config_candidates()


def find_config_file(shell: str) -> Path | None:
    """Find the appropriate config file - first existing candidate.

    Args:
        shell: Shell name ('bash' or 'zsh')

    Returns:
        Path to config file, or None if no candidates exist
    """
    candidates = get_shell_config_candidates(shell)
    return candidates[0] if candidates else None


def _has_any_marker(content: str) -> bool:
    """Check if content contains any completion marker (current or legacy)."""
    return COMPLETION_MARKER_START in content or _LEGACY_MARKER_START in content


def is_completion_installed(config_path: Path) -> bool:
    """Check if completion is already installed in config file.

    Args:
        config_path: Path to shell config file

    Returns:
        True if any completion marker (current or legacy) found in file
    """
    if not config_path.exists():
        return False

    content = config_path.read_text(encoding="utf-8")
    return _has_any_marker(content)


def is_legacy_completion_block(config_path: Path) -> bool:
    """Check if the installed completion block uses the legacy format.

    Legacy format: old markers or missing `command -v` guard.
    """
    if not config_path.exists():
        return False

    content = config_path.read_text(encoding="utf-8")
    if _LEGACY_MARKER_START in content:
        return True
    if COMPLETION_MARKER_START in content and "command -v" not in content:
        # PowerShell blocks use Get-Command, not command -v
        if "Get-Command" in content:
            return False
        return True
    return False


def generate_completion_script(shell: str) -> str:
    """Generate completion script with shell-native aliasing.

    Uses ai-agent-rules (unshadowed by Hermit) as the canonical binary,
    then aliases the completion function to ai-rules via compdef/complete.

    Args:
        shell: Shell name ('bash' or 'zsh')

    Returns:
        Completion script to add to shell config

    Raises:
        ValueError: If shell is not supported
    """
    env_var = f"_{CANONICAL_CMD.upper().replace('-', '_')}_COMPLETE"

    if shell == "powershell":
        # bash_source mode: Click reads COMP_WORDS (space-separated command line)
        # and COMP_CWORD (0-based index of current word) to return completions.
        return f"""{COMPLETION_MARKER_START}
if (Get-Command {CANONICAL_CMD} -ErrorAction SilentlyContinue) {{
    Register-ArgumentCompleter -Native -CommandName '{CANONICAL_CMD}','{ALIAS_CMD}' -ScriptBlock {{
        param($wordToComplete, $commandAst, $cursorPosition)
        $words = $commandAst.CommandElements | ForEach-Object {{ $_.ToString() }}
        $env:{env_var} = 'bash_complete'
        $env:COMP_WORDS = $words -join ' '
        if ($wordToComplete -eq '') {{
            $env:COMP_CWORD = $words.Count
        }} else {{
            $env:COMP_CWORD = $words.Count - 1
        }}
        try {{
            $completions = & {CANONICAL_CMD} 2>$null
            $completions | ForEach-Object {{
                $parts = $_ -split ',', 2
                $text = if ($parts.Count -gt 1) {{ $parts[1] }} else {{ $parts[0] }}
                $desc = $text
                [System.Management.Automation.CompletionResult]::new($text, $text, 'ParameterValue', $desc)
            }}
        }} finally {{
            Remove-Item Env:{env_var} -ErrorAction SilentlyContinue
            Remove-Item Env:COMP_WORDS -ErrorAction SilentlyContinue
            Remove-Item Env:COMP_CWORD -ErrorAction SilentlyContinue
        }}
    }}
}}
{COMPLETION_MARKER_END}"""

    from click.shell_completion import get_completion_class

    comp_cls = get_completion_class(shell)
    if comp_cls is None:
        raise ValueError(f"Unsupported shell: {shell}")

    if shell == "zsh":
        return f"""{COMPLETION_MARKER_START}
if command -v {CANONICAL_CMD} >/dev/null 2>&1; then
  eval "$({env_var}=zsh_source {CANONICAL_CMD})"
  compdef _ai_agent_rules_completion {ALIAS_CMD}
fi
{COMPLETION_MARKER_END}"""
    else:
        return f"""{COMPLETION_MARKER_START}
if command -v {CANONICAL_CMD} >/dev/null 2>&1; then
  eval "$({env_var}=bash_source {CANONICAL_CMD})"
  complete -o nosort -F _ai_agent_rules_completion {ALIAS_CMD}
fi
{COMPLETION_MARKER_END}"""


def _resolve_config_path(shell: str) -> tuple[Path | None, str | None]:
    """Resolve config path for a shell, with PowerShell profile fallback.

    Returns (path, error_message). On success error_message is None.
    """
    config_path = find_config_file(shell)
    if config_path is None and shell == "powershell":
        profile = _get_powershell_profile_path()
        if profile is None:
            return (
                None,
                "PowerShell is not installed (neither pwsh nor powershell found)",
            )
        config_path = profile
    if config_path is None:
        return None, f"No {shell} config file found"
    return config_path, None


def install_completion(shell: str, dry_run: bool = False) -> tuple[bool, str]:
    """Install completion to shell config file.

    Args:
        shell: Shell name (e.g., 'bash', 'zsh')
        dry_run: If True, only show what would be done

    Returns:
        Tuple of (success: bool, message: str)
    """
    if shell not in SHELL_REGISTRY:
        supported = ", ".join(get_supported_shells())
        return False, f"Unsupported shell: {shell}. Supported: {supported}"

    config_path, err = _resolve_config_path(shell)
    if err:
        return False, err
    if config_path is None:
        return (
            False,
            f"No {shell} config file found. Expected one of: "
            + ", ".join(str(p) for p in get_shell_config_candidates(shell)),
        )
    if shell == "powershell" and not config_path.exists() and not dry_run:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.touch()

    if is_completion_installed(config_path):
        if is_legacy_completion_block(config_path):
            return update_completion(shell, dry_run=dry_run)
        return True, f"Completion already installed in {config_path}"

    script = generate_completion_script(shell)

    if dry_run:
        return True, f"Would append completion script to {config_path}"

    try:
        with config_path.open("a", encoding="utf-8") as f:
            f.write(f"\n{script}\n")
        return (
            True,
            f"Completion installed to {config_path}. Restart your shell or run: source {config_path}",
        )
    except Exception as e:
        return False, f"Failed to write to {config_path}: {e}"


def update_completion(shell: str, dry_run: bool = False) -> tuple[bool, str]:
    """Replace existing completion block with a freshly generated one."""
    config_path, err = _resolve_config_path(shell)
    if err or config_path is None:
        return False, err or f"No {shell} config file found"
    if not is_completion_installed(config_path):
        return install_completion(shell, dry_run=dry_run)

    new_script = generate_completion_script(shell)
    if dry_run:
        return True, f"Would update completion in {config_path}"

    content = config_path.read_text(encoding="utf-8")

    start_re = (
        re.escape(COMPLETION_MARKER_START) + "|" + re.escape(_LEGACY_MARKER_START)
    )
    end_re = re.escape(COMPLETION_MARKER_END) + "|" + re.escape(_LEGACY_MARKER_END)
    pattern = f"({start_re}).*?({end_re})"
    new_content, n = re.subn(pattern, new_script, content, flags=re.DOTALL)
    if n == 0:
        return False, f"Could not find completion block in {config_path}"
    config_path.write_text(new_content, encoding="utf-8")
    return (
        True,
        f"Completion updated in {config_path}. Restart your shell or run: source {config_path}",
    )


def uninstall_completion(config_path: Path) -> tuple[bool, str]:
    """Remove all completion blocks (current and legacy) from shell config file.

    Args:
        config_path: Path to shell config file

    Returns:
        Tuple of (success: bool, message: str)
    """
    if not config_path.exists():
        return False, f"Config file not found: {config_path}"

    if not is_completion_installed(config_path):
        return True, f"Completion not installed in {config_path}"

    try:
        content = config_path.read_text(encoding="utf-8")

        start_re = (
            re.escape(COMPLETION_MARKER_START) + "|" + re.escape(_LEGACY_MARKER_START)
        )
        end_re = re.escape(COMPLETION_MARKER_END) + "|" + re.escape(_LEGACY_MARKER_END)
        pattern = f"({start_re}).*?({end_re})"
        new_content = re.sub(pattern, "", content, flags=re.DOTALL)

        # Clean up extra blank lines left behind
        new_content = re.sub(r"\n{3,}", "\n\n", new_content)

        config_path.write_text(new_content, encoding="utf-8")
        return True, f"Completion removed from {config_path}"
    except Exception as e:
        return False, f"Failed to modify {config_path}: {e}"
