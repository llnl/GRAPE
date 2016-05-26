import option, utility, grapeMenu
import grapeGit as git
import merge
#merge a remote branch into this branch
class MergeRemote(option.Option):
    """
    grape mr (merge remote branch). If the remote branch is different from your current branch, this will update
    or add a local version of that branch, then merge it into your current branch. If you perform a grape mr on the
    current branch or if the remote branch can not be fastforward merged into your local version of that branch,
    then this will do a merge assuming the remote branch has a different line of development than
    your local branch. (Ideal for developers working on shared branches.)

    Usage: grape-mr [<branch>] [--am | --as | --at | --aT | --ay | --aY | --askAll] [--continue] [--noRecurse] [--noUpdate] [--squash]


    Options:
        --am                    Perform the merge using git's default strategy.
        --as                    Perform the merge issuing conflicts on any file modified by both branches.
        --at                    Perform the merge using the remote branch's version for any file modified by both branches.
        --aT                    Perform the merge resolving conficts using the remote branch's version. 
        --ay                    Perform the merge resolving conflicts using your topic branch's version.
        --aY                    Perform the merge using your topic branch's version for any file modified by both branches.
        --askAll                Ask to determine the merge strategy before merging each subproject.
        --noRecurse             Perform the merge in the current repository only. Otherwise, this will call
                                grape md --public=<branch> to handle submodule and nested project merges. 
        --continue              Resume your previous merge after resolving conflicts.
        --squash                Perform squash merges. 
        
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
            for e, r in zip(mre.exceptions(), mre.repos()):
                if e.commError:
                    commErrorRepos.append(r)
                    commError = True
                
            if commError:
                utility.printMsg("ERROR: can't communicate with remotes for %s. Halting remote merge." % commErrorRepos)
                return False
            
            
        
        
        # update our local reference to the remote branch so long as it's fast-forwardable or we don't have it yet..)
        hasRemote = ("origin/%s" % otherBranch) in git.remoteBranches()
        hasBranch = git.hasBranch(otherBranch)
        currentBranch = git.currentBranch()
        remoteUpToDateWithLocal = git.branchUpToDateWith("remotes/origin/%s" % otherBranch, otherBranch)
        updateLocal =  hasRemote and  (remoteUpToDateWithLocal or not hasBranch) and currentBranch != otherBranch
        if  updateLocal:
            utility.printMsg("updating local branch %s from %s" % (otherBranch, "origin/%s" % otherBranch))
            utility.MultiRepoCommandLauncher(updateBranchHelper, branch=otherBranch).launchFromWorkspaceDir(handleMRE=updateBranchHandleMRE)
        
        args["<branch>"] = otherBranch if updateLocal else "origin/%s" % otherBranch
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

def updateBranchHelper(repo="unknown", branch="master"):
    utility.printMsg("Updating local reference to %s in %s" % (branch, repo))
    return git.fetch("origin %s:%s" % (branch, branch))
    
def updateBranchHandleMRE(mre):
    for e, repo, branch in zip(mre.exceptions(), mre.repos(), mre.branches()):
        if "Couldn't find remote ref" in e.gitOutput:
            utility.printMsg("Remote reference to %s not present in %s. Remote ref must be present in all active submodules to merge.\n\t"
                             "Either create placeholder branches or deactivate submodules to resolve. " % (branch, repo))
    raise mre
    
