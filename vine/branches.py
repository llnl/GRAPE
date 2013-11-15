import option
if not ".." in sys.path:
    sys.path.append( ".." )
import git

# list local branches (git branch)
class Branches(option.Option):
    key = 'b'
    section = " MISCELLANEOUS "

    def Description(self):
        return "List all of your local repo's branches"

    def Execute(self):
        git.branch()
        return Tru
