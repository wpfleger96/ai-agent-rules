from pathlib import Path

import pytest

from ai_rules.state import get_active_profile, get_state, set_active_profile


@pytest.fixture
def state_setup(tmp_path, monkeypatch):
    """Setup fixture for state management tests."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(Path, "home", staticmethod(lambda: home))

    state_dir = home / ".ai-agent-rules"
    state_dir.mkdir()

    return {
        "home": home,
        "state_dir": state_dir,
        "state_file": state_dir / "state.yaml",
    }


@pytest.mark.unit
@pytest.mark.state
class TestStateManagement:
    """Test state management functionality."""

    def test_get_state_returns_empty_dict_when_no_file(self, state_setup):
        """Test that get_state returns empty dict when state file doesn't exist."""
        assert get_state() == {}

    def test_get_active_profile_returns_none_when_no_state(self, state_setup):
        """Test that get_active_profile returns None when no state exists."""
        assert get_active_profile() is None

    def test_set_active_profile_creates_state_file(self, state_setup):
        """Test that set_active_profile creates state file with profile."""
        set_active_profile("work")

        state_file = state_setup["state_file"]
        assert state_file.exists()

        state = get_state()
        assert state["active_profile"] == "work"
        assert "last_install" in state

    def test_set_active_profile_updates_existing_state(self, state_setup):
        """Test that set_active_profile updates existing state."""
        set_active_profile("default")
        assert get_active_profile() == "default"

        set_active_profile("work")
        assert get_active_profile() == "work"

    def test_set_profile_includes_timestamp(self, state_setup):
        """Test that set_active_profile includes a timestamp."""
        set_active_profile("work")

        state = get_state()
        assert "last_install" in state
        assert isinstance(state["last_install"], str)
        assert "+00:00" in state["last_install"] or state["last_install"].endswith("Z")
