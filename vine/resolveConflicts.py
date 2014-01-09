import subprocess, sys
import option
import grapeGit as git

# resolve conflicts using git mergetool
class ResolveConflicts(option.Option):
    def __init__(self):
        self._key = "resolve"
        self._section = "Merge"

    def description(self):
        return "Resolve Conflicts that arose as result of a merge or a rebase"

    def execute(self):
        p = subprocess.Popen("git mergetool",shell=True)
        p.wait()
        # print out git status, which contains instructions to complete a merge
        git.status()
        return True

