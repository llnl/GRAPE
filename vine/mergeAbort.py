import option
if not ".." in sys.path:
    sys.path.append( ".." )
import git

# abort a merge
class MergeAbort(option.Option):
    key = 'abort'
    section = " MERGE "

    def Description(self):
        return "abort current merge"

    def Execute(self):
        git.merge("--abort")
