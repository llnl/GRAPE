import subprocess, sys
import option
if not ".." in sys.path:
    sys.path.append( ".." )
import git

# resolve conflicts using git mergetool
class ResolveConflicts(option.Option):
    key = 'resolve'
    section = " MERGE "

    def Description(self):
        return "Resolve Conflicts that arose as result of a merge or a rebase"

    def Execute(self):
        p = subprocess.Popen("git mergetool",shell=True)
        p.wait()
        # print out git status, which contains instructions to complete a merge
        git.status()
        return Tru
