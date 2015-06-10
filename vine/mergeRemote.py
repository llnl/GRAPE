import option, utility, grapeMenu
import grapeGit as git
import merge
#merge a remote branch into this branch
class MergeRemote(option.Option):
    """
    grape mr (merge remote branch). If the remote branch is different from your current branch, this will update
    or add a local version of that branch, then merge it into your current branch. If you perform a grape mr on the
    current branch, then this will do a merge assuming the remote branch has a different line of development than
    your local branch. (Ideal for developers working on shared branches.)

    Usage: grape-mr [<branch>] [--am | --as | --at | --ay] [--continue] [--noRecurse] [--noUpdate]


    Options:
        --am                    Perform the merge using git's default strategy.
        --as                    Perform the merge issuing conflicts on any file modified by both branches.
        --at                    Perform the merge resolving conficts using the public branch's version. 
        --ay                    Perform the merge resolving conflicts using your topic branch's version.
        --noRecurse             Perform the merge in the current repository only. Otherwise, this will call
                                grape md --public=<branch> to handle submodule and nested project merges. 
        --continue              Resume your previous merge after resolving conflicts.
        
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
        if not "<<cmd>>" in args:
            args["<<cmd>>"] = "mr"
        otherBranch = args['<branch>']
        if not otherBranch:
            # list remote branches that are available
            print git.branch('-r')
            otherBranch = utility.userInput("Enter name of branch you would like to merge into this branch (without the origin/ prefix)")

        # make sure remote references are up to date
        utility.printMsg("Fetching remote references in all projects...")
        try:
            utility.MultiRepoCommandLauncher(fetchHelper).launchFromWorkspaceDir()
        except utility.MultiRepoException as mre:
            commError = False
            commErrorRepos = []
            for e, r in zip(mre, mre.repos):
                if e.commError:
                    commErrorRepos.append(r)
                    commError = True
                
            if commError:
                utility.printMsg("ERROR: can't communicate with remotes for %s. Halting remote merge." % commErrorRepos)
                return False
            
            
        
        
        # update our local reference to the remote branch so long as it's fast-forwardable or we don't have it yet..)
        hasRemote = git.hasBranch("origin/%s" % otherBranch)
        hasBranch = git.hasBranch(otherBranch)
        currentBranch = git.currentBranch()
        if  hasRemote and  (git.branchUpToDateWith(otherBranch, "origin/%s" % otherBranch) or not hasBranch) and currentBranch != otherBranch:
            utility.MultiRepoCommandLauncher(updateBranchHelper, branch=otherBranch).launchFromWorkspaceDir()
            
        args["<branch>"] = otherBranch if currentBranch != otherBranch else "origin/%s" % otherBranch
        # we've handled the update, we don't want m or md to update the local branch. 
        args["--noUpdate"] = True
        # if mr is called by the user, need to initialize the --continue argument. 
        # if it is called by md, it will be set already. 
        if not "--continue" in args:
            args["--continue"] = False        
        
        return grapeMenu.menu().getOption('m').execute(args)

    def setDefaultConfig(self, config):
        pass

def fetchHelper():
    return git.fetch("origin", warnOnCommError=False, raiseOnCommError=True)

def updateBranchHelper(branch, repo):
    utility.printMsg("Updating local reference to %s in %s", (branch, repo))
    return git.fetch("origin %s:%s" % (branch, branch))
    
    