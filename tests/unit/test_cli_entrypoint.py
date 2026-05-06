import os
import subprocess
import sys

from pathlib import Path

import pytest


@pytest.mark.unit
def test_cli_package_supports_module_execution() -> None:
    repo_root = Path(__file__).parents[2]
    src_path = repo_root / "src"
    existing_pythonpath = os.environ.get("PYTHONPATH")
    pythonpath = (
        str(src_path)
        if not existing_pythonpath
        else os.pathsep.join([str(src_path), existing_pythonpath])
    )

    result = subprocess.run(
        [sys.executable, "-m", "ai_rules.cli", "--help"],
        capture_output=True,
        text=True,
        check=False,
        cwd=repo_root,
        env={**os.environ, "PYTHONPATH": pythonpath},
        timeout=10,
    )

    assert result.returncode == 0
    assert "Usage:" in result.stdout
    assert "install" in result.stdout
