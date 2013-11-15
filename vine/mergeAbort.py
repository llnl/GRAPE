import sys
import option
if not ".." in sys.path:
    sys.path.append( ".." )
import git

# abort a merge
class MergeAbort(option.Option):
    def __init__(self):
        self._key = "abort"
        self._section = "Merge"

    def description(self):
        return "abort current merge"

    def execute(self):
        git.merge("--abort")
