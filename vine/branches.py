import sys, os
import grapeGit as git
import option

# list local branches (git branch)
class Branches(option.Option):
    def __init__(self):
        super(Branches,self).__init__()
        self._key = "b"
        self._section = "Workspace"

    def description(self):
        return "List all of your local repo's branches"

    def execute(self, args):
        os.environ["GIT_PYTHON_TRACE"] = "full"
        print(git.branch())
        return True

    def setDefaultConfig(self, config):
        pass
