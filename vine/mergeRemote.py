import option, utility
import grapeGit as git
import merge
#merge a remote branch into this branch
class MergeRemote(option.Option):
    """
    grape mr (merge remote branch)
    Usage: grape-mr [<branch>] [--am | --as | --at | --ay]

    Arguments:
    <branch>      The name of the remote branch to merge in (without remote/origin or origin/ prefix)
    
    """
    def __init__(self):
        self._key = "mr"
        self._section = "Merge"

    def description(self):
        return "Merge a remote branch into your current branch."

    def execute(self,args):
        otherBranch = args['<branch>']
        if not otherBranch:
            # list remote branches that are available
            git.branch('-r')
            otherBranch = utility.userInput("Enter name of branch you would like to merge into this branch (without the origin/ prefix)")

        return merge.mergeIntoCurrent("origin/%s" % otherBranch, args)

    def setDefaultConfig(self, config):
        pass
