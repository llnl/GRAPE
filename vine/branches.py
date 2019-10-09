import logging
import os
from vine import grapeGit as git
from vine.option import Option
from vine.command_path_handler import CommandPathHandler
from vine.vine_logging import log_wrapper

# list local branches (git branch)
class Branches(Option, CommandPathHandler):

    def __init__(self):
        super(Branches, self).__init__()
        self._key = "b"
        self._section = "Workspace"

    def description(self):
        return "List all of your local repo's branches"

    @log_wrapper
    def execute(self, args):
        os.environ["GIT_PYTHON_TRACE"] = "full"
        # Branches logged & printed during vine_subprocess.executeSubProcess()
        branches = git.branch(execution_path=self.command_path)
        logging.info(f'\n{branches}')
        return True

    def setDefaultConfig(self, config):
        pass
