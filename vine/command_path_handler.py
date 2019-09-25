from contextlib import contextmanager
import logging
import os


class CommandPathHandler(object):
    """Paths referenced by git commands when executed.

    Set 'command_path' to a directory where a user would manually run a git
    command. 'workspace_dir' is automatically dervied from the given
    'command_path' and represents GRAPE's concept of a workspace.

    Assigning paths to command objects allows multiple git commands to run
    asynchronously in multiple directories.
    """

    WORKSPACE_DIR = None
    SYS_INDEPENDENT_ROOT_DIR = os.path.abspath(os.sep)

    def __init__(self):
        super(CommandPathHandler, self).__init__()
        self._command_path = None

    @property
    def command_path(self):
        if self._command_path:
            return self._command_path
        logging.error('"command_path" in "CommandPathHandler" not set.')

    @command_path.setter
    def command_path(self, command_path):
        if not os.path.exists(command_path):
            logging.warning(f'Executable path "{command_path}" does not exist.')
        self._command_path = command_path
        self.WORKSPACE_DIR = None  # TODO: keep here??

    @property
    def workspace_dir(self):
        if not self.WORKSPACE_DIR:
            self.__set_workspace_dir()
        return self.WORKSPACE_DIR

    def __set_workspace_dir(self):
        _base_dir = self._command_path
        while _base_dir != self.SYS_INDEPENDENT_ROOT_DIR:
            if os.path.exists(os.path.join(_base_dir, '.git')):
                self.WORKSPACE_DIR = _base_dir
            _base_dir = os.path.dirname(_base_dir)

    @contextmanager
    def temp_work_in_dir(self, tmp_path):
        long_term_exec_path = self.command_path
        self.command_path = os.path.realpath(tmp_path)
        yield
        self.command_path = long_term_exec_path
