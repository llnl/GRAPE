import os

import option
import utility
import grapeGit as git
import grapeConfig


class DeleteBranch(option.Option):
    """ Deletes a topic branch both locally and on origin for all projects in this workspace. 
    Usage: grape-db [-D] [<branch>] [--verify]

    Options:
    -D              Forces the deletion of unmerged branches. If you are on the branch you
                    are trying to delete, this will detach you from the branch and then 
                    delete it, issuing a warning that you are in a detached state.  
     --verify       Verifies the delete before performing it. 

    Arguments: 
    <branch>        The branch to delete. Will ask for branch name if not included. 
    
    
    """
    def __init__(self):
        super(DeleteBranch, self).__init__()
        self._key = "db"
        self._section = "Gitflow Tasks"

    def description(self):
        return "Delete a branch on both your local repo and on origin"



    def execute(self, args):
        branch = args["<branch>"]
        force = args["-D"]
        if not branch:
            branch = utility.userInput("Enter name of branch to delete")


        if args["--verify"]:
            proceed = utility.userInput("Would you like to delete the branch %s" % branch, 'y')
            if not proceed:
                return True        
        
        launcher = utility.MultiRepoCommandLauncher(deleteBranch, 
                                                    branch=branch, 
                                                    globalArgs=[force])
        try:
            launcher.launchFromWorkspaceDir()
        except utility.MultiRepoException as e:
            handleDeleteBranchMRE(e, force)
            
        return True

    def setDefaultConfig(self, config):
        pass


    
def deleteBranch(repo='', branch='master', args = None):
    force = args[0]
    forceStr = "-D" if force is True else "-d"
    with utility.cd(repo):
        utility.printMsg("deleting %s in %s..." % (branch, repo))
        git.branch("%s %s" % (forceStr, branch))
        if "origin/%s" % branch in git.branch("-r"):
            git.push("--delete origin %s" % branch, throwOnFail=True)    

def detachThenForceDeleteBranch(repo='', branch='master', args = None):
    with utility.cd(repo):
        utility.printMsg("*** WARNING ***: Detaching in order to delete %s in %s. You will be in a headless state." % (branch, repo))
        git.checkout("--detach HEAD")
        git.branch("-D %s" % branch)
        if "origin/%s" % branch in git.remoteBranches():
            git.push("--delete origin %s" % branch, throwOnFail=False)
            
def handleDetachThenForceMRE(mre):
    # this shouldn't happen, but here is some verbosity for when it does...
    for e1, branch, repo in zip(mre.exceptions(), mre.branches(), mre.repos()):
        print e1, branch, repo
    raise mre

def handleDeleteBranchMRE(mre, force=False):
    detachTuples = []
    for e1, branch, repo in zip(mre.exceptions(), mre.branches(), mre.repos()):
        try:
            raise e1
        except git.GrapeGitError as e:
            with utility.cd(repo):
                if "Cannot delete the branch" in e.gitOutput and \
                   "which you are currently on." in e.gitOutput:
                    if force:
                        detachTuples.append((repo, branch, None))
                    else:
                        utility.printMsg("call grape db -D %s to force deletion of branch you are currently on." % branch)
                elif "not deleting branch" in e.gitOutput and "even though it is merged to HEAD." in e.gitOutput:
                    git.branch("-D %s" % branch)
                elif "error: branch" in e.gitOutput and "not found" in e.gitOutput:
                    "%s not found in %s" % (branch, repo)
                    pass
                elif "is not fully merged" in e.gitOutput:
                    if force:
                        utility.printMsg("**DELETING UNMERGED BRANCH %s" % branch)
                        git.branch("-D %s" % branch)
                    else:
                        print "%s is not fully merged in %s. Run grape db -D %s to force the deletion" % (branch, repo, branch)
                elif e.commError:
                    utility.printMsg("Could not connect to origin to delete remote references to your branch "
                                     "You may want to call grape db %s again once you've reconnected." % branch)
                else:
                    utility.printMsg("Deletion of %s failed for unhandled reason." % branch)
                    print e.gitOutput
                    raise e

    utility.MultiRepoCommandLauncher(detachThenForceDeleteBranch, 
                                    listOfRepoBranchArgTuples=detachTuples).launchFromWorkspaceDir(handleMRE=handleDetachThenForceMRE)