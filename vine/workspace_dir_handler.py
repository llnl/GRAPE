from contextlib import contextmanager
import logging
import os


class WorkspaceDirHandler:
    """Path referenced by git based commands when executed."""

    SYS_INDEPENDENT_ROOT_DIR = os.path.abspath(os.sep)
    GRAPE_CONFIG = '.grapeconfig'

    def __init__(self):
        super(WorkspaceDirHandler, self).__init__()
        self._workspace_dir = None

    @property
    def workspace_dir(self):
        if self._workspace_dir:
            return self._workspace_dir
        logging.error(f'GRAPE needs to be called from within a git repo.')
        exit(1)

    @workspace_dir.setter
    def workspace_dir(self, workspace_dir):
        """Resolve a path to the workspace GRAPE should operate on.

        Args:
            workspace_dir (str): A directory inside or at a Git workspace.
        """
        if not workspace_dir:
            return

        _base_dir = os.path.realpath(os.path.abspath(workspace_dir))
        home_dir = os.path.realpath(os.path.expanduser('~'))
        git_workspace_dir = None
        while True:
            # .grapeconfig identifies the workspace GRAPE should manage. In
            # particular, this lets a command started in a nested repository
            # continue to use the top-level workspace configuration.
            # The home config is global configuration, not a workspace marker.
            if (_base_dir != home_dir and
                    os.path.exists(os.path.join(_base_dir, self.GRAPE_CONFIG))):
                self._workspace_dir = _base_dir
                return

            # Keep the nearest Git repository as a fallback for repositories
            # that are not GRAPE workspaces and for setup before config exists.
            if (git_workspace_dir is None and
                    os.path.exists(os.path.join(_base_dir, '.git'))):
                git_workspace_dir = _base_dir

            if _base_dir == self.SYS_INDEPENDENT_ROOT_DIR:
                break
            _base_dir = os.path.dirname(_base_dir)

        if git_workspace_dir:
            self._workspace_dir = git_workspace_dir

    @contextmanager
    def temp_work_in_dir(self, tmp_path):
        long_term_exec_path = self.workspace_dir
        self._workspace_dir = os.path.realpath(tmp_path)
        yield
        self._workspace_dir = long_term_exec_path
