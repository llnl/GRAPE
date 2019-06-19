import logging
import os
import sys
import grapeGit as git
import option
from vine_logging import log_wrapper

# list local branches (git branch)
class Branches(option.Option):
    def __init__(self):
        super(Branches,self).__init__()
        self._key = "b"
        self._section = "Workspace"

    def description(self):
        return "List all of your local repo's branches"

    @log_wrapper
    def execute(self, args):
        os.environ["GIT_PYTHON_TRACE"] = "full"
        logging.info(git.branch())
        return True

    def setDefaultConfig(self, config):
        pass
