import sys,os
import option,grapeGit
if not ".." in sys.path:
    sys.path.append( ".." )


# list local branches (git branch)
class Branches(option.Option):
    def __init__(self):
        self._key = "b"
        self._section = "Miscellaneous"

    def description(self):
        return "List all of your local repo's branches"

    def execute(self):
        os.environ["GIT_PYTHON_TRACE"] = "full"
        g = grapeGit.GrapeGit()
        g.branch()
        return True
