import option
import grapeGit as git


# resolve conflicts using git mergetool
class ResolveConflicts(option.Option):
    def __init__(self):
        super(ResolveConflicts, self).__init__()
        self._key = "resolve"
        self._section = "Merge"

    def description(self):
        return "Resolve Conflicts that arose as result of a merge or a rebase"

    def execute(self, args):
        git.gitcmd("mergetool", "Mergetool Failed")
        # print out git status, which contains instructions to complete a merge
        git.status()
        return True

    def setDefaultConfig(self, config):
        pass
