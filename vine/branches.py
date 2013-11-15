import sys
import option
if not ".." in sys.path:
    sys.path.append( ".." )
import git

# list local branches (git branch)
class Branches(option.Option):
    def __init__(self):
        self._key = "b"
        self._section = "Miscellaneous"

    def description(self):
        return "List all of your local repo's branches"

    def execute(self):
        g = git.Git()
        g.branch()
        return True
