"""Writers keep user symlinks and work when HOME is spelled through one."""

import json
import os

from pathlib import Path

import pytest

from ai_rules import symlinks
from ai_rules.config import dump_config_file, write_file_atomic
from ai_rules.mcp import ClaudeMCPManager
from ai_rules.symlinks import SymlinkResult, check_symlink, create_symlink


@pytest.fixture
def aliased_home(tmp_path):
    """Return R/alias/../home, where R/alias -> R/physical/deep."""
    (tmp_path / "physical" / "deep").mkdir(parents=True)
    (tmp_path / "physical" / "home").mkdir()
    (tmp_path / "alias").symlink_to(tmp_path / "physical" / "deep")
    return tmp_path / "alias" / ".." / "home"


@pytest.mark.unit
class TestWriteFileAtomic:
    def test_writes_through_user_symlink(self, tmp_path, monkeypatch):
        dotfile = tmp_path / "dotfiles" / "claude.json"
        dotfile.parent.mkdir()
        dotfile.write_text("{}")
        dotfile.chmod(0o640)
        home = tmp_path / "home"
        home.mkdir()
        (home / ".claude.json").symlink_to(dotfile)
        monkeypatch.setenv("HOME", str(home))

        ClaudeMCPManager()._write_installed({"x": {"command": "x"}})

        assert (home / ".claude.json").is_symlink()
        assert json.loads(dotfile.read_text())["mcpServers"] == {"x": {"command": "x"}}
        assert dotfile.stat().st_mode & 0o777 == 0o640

    def test_dangling_link_creates_target_in_existing_folder(self, tmp_path):
        link = tmp_path / "link.json"
        link.symlink_to(tmp_path / "missing.json")

        write_file_atomic(link, lambda f: f.write("new"))

        assert link.is_symlink()
        assert (tmp_path / "missing.json").read_text() == "new"

    def test_dangling_link_into_missing_folder_errors_and_keeps_link(self, tmp_path):
        link = tmp_path / "link.json"
        link.symlink_to(tmp_path / "gone" / "x.json")

        with pytest.raises(OSError, match="link.json"):
            write_file_atomic(link, lambda f: f.write("new"))

        assert link.is_symlink()
        assert not (tmp_path / "gone").exists()

    def test_symlink_loop_errors_naming_the_link(self, tmp_path):
        a, b = tmp_path / "a", tmp_path / "b"
        a.symlink_to(b)
        b.symlink_to(a)

        with pytest.raises(OSError, match=str(a)):
            write_file_atomic(a, lambda f: f.write("new"))

        assert a.is_symlink() and b.is_symlink()

    def test_cache_write_under_home_alias_lands_in_physical_dir(
        self, tmp_path, aliased_home
    ):
        cache = aliased_home / ".ai-agent-rules" / "cache" / "settings.json"

        dump_config_file(cache, {"k": 1}, "json")

        physical = tmp_path / "physical" / "home"
        written = physical / ".ai-agent-rules" / "cache" / "settings.json"
        assert json.loads(written.read_text()) == {"k": 1}


@pytest.mark.unit
class TestCreateSymlinkPhysicalPaths:
    def test_relative_link_resolves_under_home_alias(self, tmp_path, aliased_home):
        source = tmp_path / "repo" / "AGENTS.md"
        source.parent.mkdir()
        source.write_text("x")
        target = aliased_home / ".claude" / "CLAUDE.md"

        result, _ = create_symlink(target, source, force=True)

        assert result == SymlinkResult.CREATED
        assert not os.path.isabs(os.readlink(target))
        assert target.resolve() == source.resolve()
        assert check_symlink(target, source)[0] == "correct"
        assert create_symlink(target, source, force=True)[0] == (
            SymlinkResult.ALREADY_CORRECT
        )

    def test_plain_home_link_is_unchanged_and_already_correct(self, tmp_path):
        source = tmp_path / "repo" / "AGENTS.md"
        source.parent.mkdir()
        source.write_text("x")
        target = tmp_path / "home" / "CLAUDE.md"
        target.parent.mkdir()
        target.symlink_to(Path("..") / "repo" / "AGENTS.md")

        result, _ = create_symlink(target, source, force=True)

        assert result == SymlinkResult.ALREADY_CORRECT
        assert os.readlink(target) == "../repo/AGENTS.md"


@pytest.fixture(params=["prefix", "alias_dotdot"])
def home_layout(request, tmp_path):
    """Return (home as spelled, physical home) for two symlinked HOME layouts."""
    physical = tmp_path / "physical" / "home"
    physical.mkdir(parents=True)
    if request.param == "prefix":
        (tmp_path / "var").symlink_to(tmp_path / "physical")
        return tmp_path / "var" / "home", physical
    (tmp_path / "physical" / "deep").mkdir()
    (tmp_path / "alias").symlink_to(tmp_path / "physical" / "deep")
    return tmp_path / "alias" / ".." / "home", physical


@pytest.mark.unit
def test_cache_source_under_symlinked_home(home_layout, monkeypatch):
    home, physical = home_layout
    source = home / ".ai-agent-rules" / "cache" / "settings.json"
    (physical / ".ai-agent-rules" / "cache").mkdir(parents=True)
    (physical / ".ai-agent-rules" / "cache" / "settings.json").write_text("{}")
    target = home / ".claude" / "settings.json"
    monkeypatch.setattr(
        "ai_rules.symlinks.console.input", lambda *_: pytest.fail("prompted")
    )

    assert create_symlink(target, source)[0] == SymlinkResult.CREATED
    assert target.resolve() == source.resolve()
    assert create_symlink(target, source)[0] == SymlinkResult.ALREADY_CORRECT
    assert check_symlink(target, source)[0] == "correct"


@pytest.mark.unit
@pytest.mark.parametrize("broken", ["loop", "missing"])
def test_invalid_parent_before_dotdot_never_collapses(tmp_path, monkeypatch, broken):
    sentinel = tmp_path / "settings.json"
    sentinel.write_text('{"keep": 1}')
    if broken == "loop":
        (tmp_path / "a").symlink_to(tmp_path / "b")
        (tmp_path / "b").symlink_to(tmp_path / "a")
    home = tmp_path / "home"
    home.mkdir()
    (home / ".claude.json").symlink_to(tmp_path / "a" / ".." / "settings.json")
    monkeypatch.setenv("HOME", str(home))

    with pytest.raises(OSError, match="claude.json"):
        ClaudeMCPManager()._write_installed({"x": {"command": "x"}})

    assert sentinel.read_text() == '{"keep": 1}'
    assert (home / ".claude.json").is_symlink()


@pytest.mark.unit
def test_source_through_missing_folder_is_an_error(tmp_path):
    (tmp_path / "file").write_text("x")
    target = tmp_path / "link"

    result, _ = create_symlink(target, tmp_path / "missing" / ".." / "file")

    assert result == SymlinkResult.ERROR
    assert not target.is_symlink()


@pytest.mark.unit
def test_cache_source_that_is_itself_a_symlink(tmp_path, monkeypatch):
    dotfile = tmp_path / "dotfiles" / "settings.json"
    dotfile.parent.mkdir()
    dotfile.write_text("{}")
    source = tmp_path / "cache" / "settings.json"
    source.parent.mkdir()
    source.symlink_to(dotfile)
    target = tmp_path / "home" / "settings.json"
    monkeypatch.setattr(
        "ai_rules.symlinks.console.input", lambda *_: pytest.fail("prompted")
    )

    assert create_symlink(target, source)[0] == SymlinkResult.CREATED
    assert os.readlink(target) == "../cache/settings.json"
    assert create_symlink(target, source)[0] == SymlinkResult.ALREADY_CORRECT
    assert check_symlink(target, source)[0] == "correct"


def _sentinel_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, Path]:
    sentinel = tmp_path / "R" / "settings.json"
    sentinel.parent.mkdir()
    sentinel.write_text('{"keep": 1}')
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    return sentinel, home / ".claude.json"


def _assert_write_refused(sentinel: Path, link: Path) -> None:
    with pytest.raises(OSError, match="claude.json"):
        ClaudeMCPManager()._write_installed({"x": {"command": "x"}})
    assert sentinel.read_text(encoding="utf-8") == '{"keep": 1}'
    assert link.is_symlink()


@pytest.mark.unit
def test_overlimit_folder_alias_chain_is_repaired_not_already_correct(tmp_path):
    source = tmp_path / "cache" / "settings.json"
    source.parent.mkdir()
    source.write_text("{}")
    alias = source.parent
    for i in range(200):
        nxt = tmp_path / f"alias{i}"
        nxt.symlink_to(alias)
        alias = nxt
        try:
            os.stat(alias / "settings.json")
        except OSError:
            break
    else:
        pytest.skip("host has no symlink depth limit below 200")
    target = tmp_path / "home" / "settings.json"
    target.parent.mkdir()
    target.symlink_to(alias / "settings.json")

    assert (
        create_symlink(target, source, force=True)[0] != SymlinkResult.ALREADY_CORRECT
    )
    assert target.resolve(strict=True) == source.resolve()
    assert check_symlink(target, source)[0] == "correct"


@pytest.mark.unit
@pytest.mark.parametrize("suffix", ["/", "/."])
@pytest.mark.parametrize("intermediate", [False, True])
def test_link_requiring_a_directory_is_refused(
    tmp_path, monkeypatch, suffix, intermediate
):
    sentinel, link = _sentinel_home(tmp_path, monkeypatch)
    first = tmp_path / "mid" if intermediate else link
    first.symlink_to(str(sentinel) + suffix)
    if intermediate:
        link.symlink_to(first)

    _assert_write_refused(sentinel, link)


@pytest.mark.unit
def test_chain_over_kernel_limit_is_refused(tmp_path, monkeypatch):
    sentinel, link = _sentinel_home(tmp_path, monkeypatch)
    head = sentinel
    for i in range(200):
        nxt = tmp_path / f"c{i}"
        nxt.symlink_to(head)
        head = nxt
        try:
            os.stat(head)
        except OSError:
            break
    else:
        pytest.skip("kernel accepted a 200-link chain")
    link.symlink_to(head)

    _assert_write_refused(sentinel, link)


@pytest.mark.unit
@pytest.mark.parametrize("broken", ["loop", "missing", "hidden"])
def test_broken_dotdot_link_is_repaired_not_already_correct(tmp_path, broken):
    source = tmp_path / "cache" / "settings.json"
    source.parent.mkdir()
    source.write_text("{}")
    if broken == "loop":
        (tmp_path / "obstacle").symlink_to(tmp_path / "obstacle")
    target = tmp_path / "home" / "settings.json"
    target.parent.mkdir()
    if broken == "hidden":
        (tmp_path / "bridge").symlink_to("missing/../cache")
        target.symlink_to("../bridge/settings.json")
    else:
        target.symlink_to(tmp_path / "obstacle" / ".." / "cache" / "settings.json")

    assert (
        create_symlink(target, source, force=True)[0] != SymlinkResult.ALREADY_CORRECT
    )
    assert target.resolve() == source.resolve()
    assert check_symlink(target, source)[0] == "correct"


@pytest.mark.unit
@pytest.mark.parametrize("suffix", ["/", "/."])
def test_dangling_link_requiring_a_directory_creates_nothing(tmp_path, suffix):
    link = tmp_path / "link.json"
    link.symlink_to(str(tmp_path / "missing.json") + suffix)

    with pytest.raises(OSError, match="link.json"):
        write_file_atomic(link, lambda f: f.write("new"))

    assert not (tmp_path / "missing.json").exists()


@pytest.mark.unit
def test_overlimit_chain_to_absent_file_is_refused(tmp_path):
    head = tmp_path / "absent.json"
    for i in range(60):
        nxt = tmp_path / f"c{i}"
        nxt.symlink_to(head)
        head = nxt
        try:
            os.stat(head)
        except FileNotFoundError:
            continue
        except OSError:
            break
    else:
        pytest.skip("kernel accepted a 60-link chain")

    with pytest.raises(OSError, match=head.name):
        write_file_atomic(head, lambda f: f.write("new"))

    assert not (tmp_path / "absent.json").exists()


@pytest.mark.unit
def test_link_switched_after_stat_is_refused(tmp_path, monkeypatch):
    first, second = tmp_path / "a.json", tmp_path / "b.json"
    first.write_text("A")
    second.write_text("B")
    link = tmp_path / "link.json"
    link.symlink_to(first)
    real_stat = os.stat

    def stat_then_switch(path, *args, **kwargs):
        result = real_stat(path, *args, **kwargs)
        if Path(path) == link and link.readlink() == first:
            link.unlink()
            link.symlink_to(second)
        return result

    monkeypatch.setattr(os, "stat", stat_then_switch)

    with pytest.raises(OSError, match="link.json"):
        write_file_atomic(link, lambda f: f.write("new"))

    assert (first.read_text(), second.read_text()) == ("A", "B")


@pytest.mark.unit
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("\\\\?\\D:\\cache\\CLAUDE.md", "D:\\cache\\CLAUDE.md"),
        ("\\\\?\\UNC\\host\\share\\x", "\\\\host\\share\\x"),
        ("..\\cache\\CLAUDE.md", "..\\cache\\CLAUDE.md"),
    ],
)
def test_read_link_drops_windows_extended_prefix(monkeypatch, raw, expected):
    link = Path("link")
    monkeypatch.setattr(os, "name", "nt")
    monkeypatch.setattr(os, "readlink", lambda _link: raw)

    assert symlinks.read_link(link) == expected
