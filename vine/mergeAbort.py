import sys
import option
import grapeGit as git

# abort a merge
class MergeAbort(option.Option):
    def __init__(self):
        super(MergeAbort, self).__init__()
        self._key = "abort"
        self._section = "Merge"

    def description(self):
        return "abort current merge"

    def execute(self,args):
        git.merge("--abort")
