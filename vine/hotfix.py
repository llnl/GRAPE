import option, sys, utility
if not ".." in sys.path:
    sys.path.append( ".." )
import git

#option that creates a hotfix branch
class Hotfix(option.Option):
    def __init__(self):
        self._key = "hot"
        self._section = "Gitflow Tasks"

    def description(self):
        return "Create a hotfix branch (for fixing weekly test failures on master)"

    def execute(self):
        git.fetch("origin","master")
        utility.createBranch("master","hot")
        return True
