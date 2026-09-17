import os

from vine.workspace_dir_handler import WorkspaceDirHandler


def _touch(path):
    with open(path, 'w', encoding='utf-8'):
        pass


def test_grapeconfig_selects_outer_workspace_from_nested_repository(tmp_path):
    """A nested Git repository uses the enclosing GRAPE workspace config."""
    workspace = tmp_path / 'workspace'
    nested = workspace / 'nested'
    nested.mkdir(parents=True)
    (workspace / '.git').mkdir()
    _touch(workspace / '.grapeconfig')
    (nested / '.git').write_text('gitdir: ../.git/nested', encoding='utf-8')

    handler = WorkspaceDirHandler()
    handler.workspace_dir = str(nested)

    assert handler.workspace_dir == os.path.realpath(str(workspace))


def test_nested_grapeconfig_selects_nested_workspace(tmp_path):
    """An independently configured nested project remains its own workspace."""
    workspace = tmp_path / 'workspace'
    nested = workspace / 'nested'
    nested.mkdir(parents=True)
    (workspace / '.git').mkdir()
    _touch(workspace / '.grapeconfig')
    (nested / '.git').mkdir()
    _touch(nested / '.grapeconfig')

    handler = WorkspaceDirHandler()
    handler.workspace_dir = str(nested)

    assert handler.workspace_dir == os.path.realpath(str(nested))


def test_nearest_git_is_fallback_without_grapeconfig(tmp_path):
    """A plain Git repository still resolves when no GRAPE config exists."""
    outer = tmp_path / 'outer'
    nested = outer / 'nested'
    nested.mkdir(parents=True)
    (outer / '.git').mkdir()
    (nested / '.git').mkdir()

    handler = WorkspaceDirHandler()
    handler.workspace_dir = str(nested)

    assert handler.workspace_dir == os.path.realpath(str(nested))


def test_home_grapeconfig_is_not_a_workspace_marker(tmp_path, monkeypatch):
    """A global home config does not define a workspace for child paths."""
    home = tmp_path / 'home'
    cwd = home / 'cwd'
    cwd.mkdir(parents=True)
    _touch(home / '.grapeconfig')
    monkeypatch.setenv('HOME', str(home))

    handler = WorkspaceDirHandler()
    handler.workspace_dir = str(cwd)

    assert handler._workspace_dir is None


def test_home_grapeconfig_does_not_override_nearest_git(tmp_path, monkeypatch):
    """A temporary Git directory remains the workspace under home config."""
    home = tmp_path / 'home'
    cwd = home / 'cwd'
    cwd.mkdir(parents=True)
    _touch(home / '.grapeconfig')
    (cwd / '.git').mkdir()
    monkeypatch.setenv('HOME', str(home))

    handler = WorkspaceDirHandler()
    handler.workspace_dir = str(cwd)

    assert handler.workspace_dir == os.path.realpath(str(cwd))
