import sys, os
import grapeGit, option

# list local branches (git branch)
class Branches(option.Option):
    def __init__(self):
        self._key = "b"
        self._section = "Miscellaneous"

    def description(self):
        return "List all of your local repo's branches"

    def execute(self,args):
        os.environ["GIT_PYTHON_TRACE"] = "full"
        grapeGit.branch()
        return True
