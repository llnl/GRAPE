import option, sys, utility
if not ".." in sys.path:
    sys.path.append( ".." )
import git

#option that creates a hotfix branch
class Hotfix(option.Option):
    key = "hot"
    section = "GITFLOW TASKS"

    def Description(self):
        return "Create a hotfix branch (for fixing weekly test failures on master)"

    def Execute(self):
        git.fetch("origin","master")
        utility.createBranch("master","hot")
        return True
