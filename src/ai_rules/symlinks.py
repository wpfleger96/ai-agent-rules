"""Symlink operations with safety checks."""

import os
import shutil

from datetime import datetime
from enum import Enum
from pathlib import Path

from ai_rules.cli.display import console, dim


def create_backup_path(target: Path) -> Path:
    """Create a timestamped backup path.

    Args:
        target: The file to backup

    Returns:
        Path with timestamp appended (e.g., file.md.ai-agent-rules-backup.20250104-143022)
    """
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return Path(f"{target}.ai-agent-rules-backup.{timestamp}")


class SymlinkResult(Enum):
    """Result of symlink operation."""

    CREATED = "created"
    ALREADY_CORRECT = "already_correct"
    UPDATED = "updated"
    SKIPPED = "skipped"
    ERROR = "error"


def create_symlink(
    target_path: Path,
    source_path: Path,
    force: bool = False,
    dry_run: bool = False,
) -> tuple[SymlinkResult, str]:
    """Create a symlink with safety checks.

    Args:
        target_path: Where the symlink should be created (e.g., ~/.CLAUDE.md)
        source_path: What the symlink should point to (e.g., repo/config/AGENTS.md)
        force: Skip confirmations
        dry_run: Don't actually create symlinks

    Returns:
        Tuple of (result, message)
    """
    target = target_path.expanduser()
    source = source_path.absolute()

    if not source.exists():
        return (
            SymlinkResult.ERROR,
            f"Source file does not exist: {source}",
        )

    if target.exists() or target.is_symlink():
        if target.is_symlink():
            current = target.resolve()
            if current == source:
                return (SymlinkResult.ALREADY_CORRECT, "Already correct")
            elif dry_run:
                return (SymlinkResult.UPDATED, f"Would update: {current} → {source}")
            elif force:
                target.unlink()
            else:
                response = console.input(
                    f"[yellow]?[/yellow] Symlink {target} exists but points to {current}\n  Replace with {source}? (y/N): "
                )
                if response.lower() != "y":
                    return (SymlinkResult.SKIPPED, "Skipped by user")
                target.unlink()
        else:
            if dry_run:
                return (
                    SymlinkResult.CREATED,
                    f"Would backup {target} and create symlink",
                )
            elif force:
                backup = create_backup_path(target)
                target.rename(backup)
                console.print(f"  {dim(f'Backed up to {backup}')}")
            else:
                response = console.input(
                    f"[yellow]?[/yellow] File {target} exists and is not a symlink\n  Replace with symlink? (y/N): "
                )
                if response.lower() != "y":
                    return (SymlinkResult.SKIPPED, "Skipped by user")
                backup = create_backup_path(target)
                target.rename(backup)
                console.print(f"  {dim(f'Backed up to {backup}')}")

    if dry_run:
        return (SymlinkResult.CREATED, f"Would create: {target} → {source}")

    target.parent.mkdir(parents=True, exist_ok=True)

    try:
        rel_source = os.path.relpath(source, target.parent)
        target.symlink_to(rel_source, target_is_directory=source.is_dir())
        return (SymlinkResult.CREATED, "Created")
    except PermissionError as e:
        return _symlink_permission_error(e)
    except FileExistsError as e:
        return (
            SymlinkResult.ERROR,
            f"File already exists: {e}\n"
            f"  {dim('Tip: Use -y to replace existing files.')}",
        )
    except (OSError, ValueError) as e:
        try:
            target.symlink_to(source, target_is_directory=source.is_dir())
            return (SymlinkResult.CREATED, "Created (absolute path)")
        except PermissionError:
            return _symlink_permission_error(e)
        except Exception as e2:
            return (
                SymlinkResult.ERROR,
                f"Failed to create symlink: {e2}\n"
                f"  {dim('Tip: Check that the target directory exists and is writable.')}",
            )


def _symlink_permission_error(e: Exception) -> tuple[SymlinkResult, str]:
    """Build a PermissionError result with platform-appropriate hints."""
    from ai_rules.platform import Platform, is_platform

    if is_platform(Platform.WINDOWS):
        return (
            SymlinkResult.ERROR,
            f"Permission denied creating symlink: {e}\n"
            f"  {dim('Windows requires Developer Mode for symlinks.')}\n"
            f"  {dim('Enable: Settings > System > For developers > Developer Mode')}\n"
            f"  {dim('Then re-run: ai-agent-rules install')}",
        )
    return (
        SymlinkResult.ERROR,
        f"Permission denied: {e}\n"
        f"  {dim('Tip: Check file permissions and ownership.')}",
    )


def create_file_copy(
    target_path: Path,
    source_path: Path,
    force: bool = False,
    dry_run: bool = False,
) -> tuple[SymlinkResult, str]:
    """Copy a file instead of symlinking.

    Used for agents that destroy symlinks (e.g., Gemini CLI on Windows).
    """
    target = target_path.expanduser()
    source = source_path.absolute()

    if not source.exists():
        return (SymlinkResult.ERROR, f"Source file does not exist: {source}")

    if target.exists() or target.is_symlink():
        if target.is_symlink():
            if dry_run:
                pass  # will be reported as CREATED below
            else:
                target.unlink()
        else:
            try:
                if target.read_bytes() == source.read_bytes():
                    return (SymlinkResult.ALREADY_CORRECT, "Already correct (copy)")
            except OSError:
                pass
            if not force:
                response = console.input(
                    f"[yellow]?[/yellow] File {target} exists\n  Overwrite with copy? (y/N): "
                )
                if response.lower() != "y":
                    return (SymlinkResult.SKIPPED, "Skipped by user")
            if not dry_run:
                backup = create_backup_path(target)
                shutil.copy2(target, backup)
                console.print(f"  {dim(f'Backed up to {backup}')}")

    if dry_run:
        return (SymlinkResult.CREATED, f"Would copy: {source} -> {target}")

    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copy2(source, target)
        return (SymlinkResult.CREATED, "Copied")
    except PermissionError as e:
        return (SymlinkResult.ERROR, f"Permission denied: {e}")
    except OSError as e:
        return (SymlinkResult.ERROR, f"Failed to copy: {e}")


def check_file_copy(target_path: Path, expected_source: Path) -> tuple[str, str]:
    """Check if a managed file copy is correct (content matches source).

    Returns same status format as check_symlink() for consistency.
    """
    target = target_path.expanduser()
    expected = expected_source.absolute()

    if not target.exists():
        return ("missing", "Not installed")

    if target.is_symlink():
        return ("not_copy", "Expected a managed copy but found a symlink")

    try:
        if target.read_bytes() == expected.read_bytes():
            return ("correct", str(expected))
        else:
            return ("stale_copy", f"Content differs from {expected}")
    except OSError:
        return ("error", "Could not read file for comparison")


def remove_file_copy(target_path: Path, force: bool = False) -> tuple[bool, str]:
    """Remove a managed file copy. Refuses to remove symlinks."""
    target = target_path.expanduser()

    if not target.exists():
        return (False, "Does not exist")

    if target.is_symlink():
        return (False, "Is a symlink, not a managed copy (refusing to delete)")

    if not force:
        response = console.input(
            f"[yellow]?[/yellow] Remove managed copy {target}? (y/N): "
        )
        if response.lower() != "y":
            return (False, "Skipped by user")

    try:
        target.unlink()
        return (True, "Removed")
    except PermissionError as e:
        return (False, f"Permission denied: {e}")
    except OSError as e:
        return (False, f"Error removing file: {e}")


def check_symlink(target_path: Path, expected_source: Path) -> tuple[str, str]:
    """Check if a symlink is correct.

    Returns:
        Tuple of (status, message) where status is one of:
        - "correct": Symlink exists and points to correct location
        - "missing": Symlink does not exist
        - "broken": Symlink exists but target doesn't exist
        - "wrong_target": Symlink points to wrong location
        - "not_symlink": File exists but is not a symlink
    """
    target = target_path.expanduser()
    expected = expected_source.absolute()

    if not target.exists() and not target.is_symlink():
        return ("missing", "Not installed")

    if not target.is_symlink():
        return ("not_symlink", "File exists but is not a symlink")

    try:
        actual = target.resolve()
    except OSError, RuntimeError:
        return ("broken", "Symlink is broken")

    if actual == expected:
        return ("correct", str(expected))
    else:
        return ("wrong_target", f"Points to {actual} instead of {expected}")


def remove_symlink(target_path: Path, force: bool = False) -> tuple[bool, str]:
    """Remove a symlink safely.

    Args:
        target_path: Path to the symlink to remove
        force: Skip confirmation

    Returns:
        Tuple of (success, message)
    """
    target = target_path.expanduser()

    if not target.exists() and not target.is_symlink():
        return (False, "Does not exist")

    if not target.is_symlink():
        return (False, "Not a symlink (refusing to delete)")

    if not force:
        response = console.input(f"[yellow]?[/yellow] Remove {target}? (y/N): ")
        if response.lower() != "y":
            return (False, "Skipped by user")

    try:
        target.unlink()
        return (True, "Removed")
    except PermissionError as e:
        return (
            False,
            f"Permission denied: {e}\n"
            f"  {dim('Tip: Check file permissions. You may need elevated privileges.')}",
        )
    except OSError as e:
        return (
            False,
            f"Error removing symlink: {e}\n"
            f"  {dim('Tip: Check that the file exists and is accessible.')}",
        )


def format_unified_diff(
    current_lines: list[str],
    expected_lines: list[str],
    from_label: str,
    to_label: str,
) -> str | None:
    """Format a unified diff with Rich markup.

    Returns:
        Formatted diff string with Rich markup, or None if no differences.
    """
    import difflib

    diff = difflib.unified_diff(
        current_lines,
        expected_lines,
        fromfile=from_label,
        tofile=to_label,
        lineterm="",
    )

    diff_lines = []
    for line in diff:
        line = line.rstrip("\n")
        if line.startswith("---") or line.startswith("+++") or line.startswith("@@"):
            diff_lines.append(f"[dim]    {line}[/dim]")
        elif line.startswith("+"):
            diff_lines.append(f"[green]    {line}[/green]")
        elif line.startswith("-"):
            diff_lines.append(f"[red]    {line}[/red]")
        else:
            diff_lines.append(f"[dim]    {line}[/dim]")

    if not diff_lines:
        return None

    return "\n".join(diff_lines)


def get_status_diff(
    status_code: str, target_path: Path, expected_source: Path
) -> str | None:
    """Content diff for a non-correct check result, or None if unavailable.

    For ``wrong_target`` the symlink is resolved to diff what it actually
    points at; for ``not_symlink``/``stale_copy`` the target file itself is
    diffed. Other status codes have no meaningful content diff.
    """
    try:
        if status_code == "wrong_target":
            return get_content_diff(target_path.resolve(), expected_source)
        if status_code in ("not_symlink", "stale_copy"):
            return get_content_diff(target_path, expected_source)
    except OSError, RuntimeError:
        pass
    return None


def get_content_diff(actual_path: Path, expected_path: Path) -> str | None:
    """Get a unified diff between two files.

    Args:
        actual_path: The actual file (where symlink currently points)
        expected_path: The expected file (where symlink should point)

    Returns:
        Formatted diff string with Rich markup, or None if identical/error
    """
    if actual_path.is_dir() and expected_path.is_dir():
        diffs = []
        actual_files = {
            p.relative_to(actual_path): p
            for p in actual_path.rglob("*")
            if p.is_file() and "__pycache__" not in p.parts
        }
        expected_files = {
            p.relative_to(expected_path): p
            for p in expected_path.rglob("*")
            if p.is_file() and "__pycache__" not in p.parts
        }

        all_files = set(actual_files.keys()) | set(expected_files.keys())
        for rel_file in sorted(all_files):
            actual_file = actual_files.get(rel_file)
            expected_file = expected_files.get(rel_file)

            if not actual_file:
                diffs.append(f"[red]    - {rel_file} (only in expected)[/red]")
            elif not expected_file:
                diffs.append(f"[green]    + {rel_file} (only in actual)[/green]")
            else:
                file_diff = get_content_diff(actual_file, expected_file)
                if file_diff:
                    diffs.append(f"    [dim]{rel_file}:[/dim]")
                    for line in file_diff.split("\n"):
                        diffs.append(f"  {line}")

        return "\n".join(diffs) if diffs else None

    try:
        with open(actual_path, "rb") as f:
            actual_bytes = f.read(8192)
            if b"\0" in actual_bytes:
                return "    [dim]Binary files differ[/dim]"

        with open(expected_path, "rb") as f:
            expected_bytes = f.read(8192)
            if b"\0" in expected_bytes:
                return "    [dim]Binary files differ[/dim]"
    except OSError:
        return None

    try:
        with open(actual_path, encoding="utf-8") as f:
            actual_lines = f.readlines()
        with open(expected_path, encoding="utf-8") as f:
            expected_lines = f.readlines()
    except OSError, UnicodeDecodeError:
        return None

    if str(actual_path).endswith(".json") and str(expected_path).endswith(".json"):
        try:
            import json

            actual_parsed = json.loads("".join(actual_lines))
            expected_parsed = json.loads("".join(expected_lines))
            if actual_parsed == expected_parsed:
                return None
            actual_lines = (
                json.dumps(actual_parsed, indent=2, sort_keys=True) + "\n"
            ).splitlines(keepends=True)
            expected_lines = (
                json.dumps(expected_parsed, indent=2, sort_keys=True) + "\n"
            ).splitlines(keepends=True)
        except json.JSONDecodeError, ValueError:
            pass

    return format_unified_diff(
        actual_lines, expected_lines, str(actual_path), str(expected_path)
    )
