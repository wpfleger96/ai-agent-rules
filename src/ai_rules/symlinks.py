"""Symlink operations with safety checks."""

import os

from datetime import datetime
from enum import Enum
from pathlib import Path

from rich.console import Console

console = Console()


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
                console.print(f"  [dim]Backed up to {backup}[/dim]")
            else:
                response = console.input(
                    f"[yellow]?[/yellow] File {target} exists and is not a symlink\n  Replace with symlink? (y/N): "
                )
                if response.lower() != "y":
                    return (SymlinkResult.SKIPPED, "Skipped by user")
                backup = create_backup_path(target)
                target.rename(backup)
                console.print(f"  [dim]Backed up to {backup}[/dim]")

    if dry_run:
        return (SymlinkResult.CREATED, f"Would create: {target} → {source}")

    target.parent.mkdir(parents=True, exist_ok=True)

    try:
        rel_source = os.path.relpath(source, target.parent)
        target.symlink_to(rel_source)
        return (SymlinkResult.CREATED, "Created")
    except PermissionError as e:
        return (
            SymlinkResult.ERROR,
            f"Permission denied: {e}\n"
            "  [dim]Tip: Check file permissions and ownership. "
            "You may need to remove existing files manually.[/dim]",
        )
    except FileExistsError as e:
        return (
            SymlinkResult.ERROR,
            f"File already exists: {e}\n"
            "  [dim]Tip: Use -y to replace existing files.[/dim]",
        )
    except (OSError, ValueError) as e:
        try:
            target.symlink_to(source)
            return (SymlinkResult.CREATED, "Created (absolute path)")
        except PermissionError:
            return (
                SymlinkResult.ERROR,
                f"Permission denied: {e}\n"
                "  [dim]Tip: Check file permissions and ownership.[/dim]",
            )
        except Exception as e2:
            return (
                SymlinkResult.ERROR,
                f"Failed to create symlink: {e2}\n"
                "  [dim]Tip: Check that the target directory exists and is writable.[/dim]",
            )


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
    except (OSError, RuntimeError):
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
            "  [dim]Tip: Check file permissions. You may need elevated privileges.[/dim]",
        )
    except OSError as e:
        return (
            False,
            f"Error removing symlink: {e}\n"
            "  [dim]Tip: Check that the file exists and is accessible.[/dim]",
        )


def get_content_diff(actual_path: Path, expected_path: Path) -> str | None:
    """Get a unified diff between two files.

    Args:
        actual_path: The actual file (where symlink currently points)
        expected_path: The expected file (where symlink should point)

    Returns:
        Formatted diff string with Rich markup, or None if identical/error
    """
    import difflib

    if actual_path.is_dir() and expected_path.is_dir():
        diffs = []
        actual_files = {
            p.relative_to(actual_path): p for p in actual_path.rglob("*") if p.is_file()
        }
        expected_files = {
            p.relative_to(expected_path): p
            for p in expected_path.rglob("*")
            if p.is_file()
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
    except (OSError, UnicodeDecodeError):
        return None

    if str(actual_path).endswith(".json") and str(expected_path).endswith(".json"):
        try:
            import json

            actual_parsed = json.loads("".join(actual_lines))
            expected_parsed = json.loads("".join(expected_lines))
            if actual_parsed == expected_parsed:
                return None
            actual_lines = (json.dumps(actual_parsed, indent=2) + "\n").splitlines(
                keepends=True
            )
            expected_lines = (json.dumps(expected_parsed, indent=2) + "\n").splitlines(
                keepends=True
            )
        except (json.JSONDecodeError, ValueError):
            pass

    diff = difflib.unified_diff(
        actual_lines,
        expected_lines,
        fromfile=str(actual_path),
        tofile=str(expected_path),
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
