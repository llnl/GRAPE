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

    @staticmethod
    def deleteBranch(branch, force=False):
        forceStr = "-D" if force else "-d"
        try: 
            git.branch("%s %s" % (forceStr, branch))
        except git.GrapeGitError as e:
            if forceStr == "-D" and "Cannot delete the branch" in e.gitOutput and \
                                    "which you are currently on." in e.gitOutput:
                utility.printMsg("*** WARNING ***: Detaching in order to delete current branch. You will be in a headless state.")
                git.checkout("--detach %s" % branch)
                git.branch("-D %s" % branch)
            elif "not deleting branch" in e.gitOutput and "even though it is merged to HEAD." in e.gitOutput:
                git.branch("-D %s" % branch)
            else: 
                print e.gitOutput
        try:
            if "origin/%s" % branch in git.branch("-r"):
                try:
                    git.push("--delete origin %s" % branch, throwOnFail=True)
                except git.GrapeGitError as e:
                    if e.commError:
                        utility.printMsg("Could not connect to origin to delete remote references to your branch "
                                         "You may want to call grape db %s again once you've reconnected." % branch)
                    else:
                        utility.printMsg("Remote branch deletion of %s failed for unhandled reason." % branch)
                        raise e
        except git.GrapeGitError as e:
            print e.gitOutput

    def execute(self, args):
        branch = args["<branch>"]
        force = args["-D"]
        if not branch:
            branch = utility.userInput("Enter name of branch to delete")
        
        wsDir = utility.workspaceDir()
        os.chdir(wsDir)
        if args["--verify"]:
            proceed = utility.userInput("Would you like to delete the branch %s" % branch, 'y')
            if not proceed:
                return True
        # delete the branch in submodules first
        submodules = git.getActiveSubmodules()
        config = grapeConfig.grapeConfig()
        subpublicmapping = config.getMapping("workspace", "submoduletopicprefixmappings")
        if submodules:
            utility.printMsg("deleting branches from submodules")

        for sub in submodules:
            utility.printMsg("deleting branch %s in %s" % (branch, sub))
            os.chdir(os.path.join(wsDir, sub))
            if git.currentBranch() == branch:
                git.checkout(subpublicmapping[git.branchPrefix(branch)])
            self.deleteBranch(branch, force)
        os.chdir(wsDir)
        
        # then the branch in nested subprojects
        subprojects = grapeConfig.GrapeConfigParser.getAllActiveNestedSubprojectPrefixes()
        if subprojects:
            utility.printMsg("Deleting %s from your active nested subprojects: " % branch)
        for sub in subprojects:
            os.chdir(os.path.join(wsDir,sub))
            utility.printMsg("deleting branch %s in %s" % (branch, sub))
            if git.currentBranch() == branch:
                git.checkout(config.getPublicBranchFor(branch))
            self.deleteBranch(branch, force)
            os.chdir(wsDir)
        
        # then the outer level repository. 
        print("GRAPE: deleting branch from outer workspace")
        self.deleteBranch(branch, force)

        return True

    def setDefaultConfig(self, config):
        pass
