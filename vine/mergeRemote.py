import option, utility, grapeMenu
import grapeGit as git
import merge
#merge a remote branch into this branch
class MergeRemote(option.Option):
    """
    grape mr (merge remote branch). Updates the branch you're merging from and then performs the merge.
    Usage: grape-mr [<branch>] [--am | --as | --at | --ay] [-v] [--quiet]

    Arguments:
    <branch>      The name of the remote branch to merge in (without remote/origin or origin/ prefix)
    
    """
    def __init__(self):
        super(MergeRemote, self).__init__()
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
        git.fetch("origin")
        # update our local reference to the remote branch so long as it's fast-forwardable or we don't have it yet..)
        hasRemote = git.hasBranch("origin/%s" % otherBranch)
        hasBranch = git.hasBranch(otherBranch)
        if  hasRemote and  (git.branchUpToDateWith(otherBranch, "origin/%s" % otherBranch) or not hasBranch):
            git.fetch("origin %s:%s" % (otherBranch, otherBranch))
        args["<branch>"] = otherBranch
        # if mr is called by the user, need to initialize the --continue argument. 
        # if it is called by md, it will be set already. 
        if not "--continue" in args:
            args["--continue"] = False
        return grapeMenu.menu().getOption('m').execute(args)

    def setDefaultConfig(self, config):
        pass
