import os

import option
import utility
import grapeGit as git
import grapeConfig


class DeleteBranch(option.Option):
    """ Deletes a topic branch both locally and on origin for all projects in this workspace. 
    Usage: grape-db [-D] [<branch>]

    Options:
    -D              Forces the deletion of unmerged branches. If you are on the branch you
                    are trying to delete, this will detach you from the branch and then 
                    delete it, issuing a warning that you are in a detached state.  

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
            git.branch("%s %s" % (forceStr, branch), quiet=True)
        except git.GrapeGitError as e:
            if forceStr == "-D" and "Cannot delete the branch" in e.gitOutput and \
                                    "which you are currently on." in e.gitOutput:
                utility.printMsg("*** WARNING ***: Detaching in order to delete current branch. You will be in a headless state.")
                git.checkout("--detach %s" % branch)
                git.branch("-D %s" % branch, quiet=True)
            else: 
                print e.gitOutput
        try:
            if "origin/%s" % branch in git.branch("-r", quiet=True): 
                git.push("--delete origin %s" % branch, quiet=True)
        except git.GrapeGitError as e:
            print e.gitOutput

    def execute(self, args):
        branch = args["<branch>"]
        force = args["-D"]
        if not branch:
            branch = utility.userInput("Enter name of branch to delete")
        
        cwd = utility.workspaceDir()
        os.chdir(cwd)
        # delete the branch in submodules first
        submodules = git.getActiveSubmodules()
        config = grapeConfig.grapeConfig()
        subpublicmapping = config.getMapping("workspace", "submoduletopicprefixmappings")
        if submodules:
            print("GRAPE: deleting branches from submodules")

        for sub in submodules:
            os.chdir(os.path.join(cwd, sub))
            if git.currentBranch() == branch:
                git.checkout(subpublicmapping[git.branchPrefix(branch)])
            self.deleteBranch(branch, force)
        os.chdir(cwd)
        
        # then the branch in nested subprojects
        subprojects = grapeConfig.GrapeConfigParser.getAllActiveNestedSubprojectPrefixes()
        if subprojects:
            utility.printMsg("Deleting %s from your active nested subprojects: " % branch)
        for sub in subprojects:
            os.chdir(os.path.join(cwd,sub))
            self.deleteBranch(branch, force)
            os.chdir(cwd)
        
        # then the outer level repository. 
        print("GRAPE: deleting branch from outer workspace")
        self.deleteBranch(branch, force)

        return True

    def setDefaultConfig(self, config):
        pass
