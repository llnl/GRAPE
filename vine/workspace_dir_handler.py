from contextlib import contextmanager
import logging
import os


class WorkspaceDirHandler:
    """Path referenced by git based commands when executed."""

    SYS_INDEPENDENT_ROOT_DIR = os.path.abspath(os.sep)

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
        _base_dir = workspace_dir
        while _base_dir:
            if os.path.exists(os.path.join(_base_dir, '.git')):
                self._workspace_dir = _base_dir
            if _base_dir == self.SYS_INDEPENDENT_ROOT_DIR:
                break
            _base_dir = os.path.dirname(_base_dir)

    @contextmanager
    def temp_work_in_dir(self, tmp_path):
        long_term_exec_path = self.workspace_dir
        self._workspace_dir = os.path.realpath(tmp_path)
        yield
        self._workspace_dir = long_term_exec_path
