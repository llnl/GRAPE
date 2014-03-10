import os, sys
import grapeConfig
import option, utility
import grapeGit as git

class DeleteBranch(option.Option):
    """ Deletes a topic branch both locally and on origin for all projects in this workspace. 
    Usage: grape-db [-D] [<branch>]

    Options:
    -D              Forces the deletion of unmerged branches. 

    Arguments: 
    <branch>        The branch to delete. Will ask for branch name if not included. 
    
    
    """
    def __init__(self):
        self._key = "db"
        self._section = "Gitflow Tasks"

    def description(self):
        return "Delete a branch on both your local repo and on origin"

    def deleteBranch(self,branch,force=False):
        forceStr = "-D" if force else "-d"
        try: 
            git.branch("%s %s" % (forceStr,branch),quiet=True)
        except git.GrapeGitError as e:
            print e.gitOutput
        try:
            git.push("--delete origin %s" % branch,quiet=True)
            print("branch successfully deleted from origin")
        except git.GrapeGitError as e:
            print e.gitOutput
            #print("could not delete from remote. Either it doesn't exist there, it is a protected branch, or you don't have a connection to origin")
            pass



    def execute(self,args):
        branch = args["<branch>"]
        force = args["-D"]
        if not branch:
            branch = utility.userInput("Enter name of branch to delete")
        
        cwd = utility.workspaceDir()
        os.chdir(cwd)
        # delete the branch in submodules first
        for sub in git.getSubmodules(): 
            os.chdir(os.path.join(cwd,sub))
            self.deleteBranch(force)
        os.chdir(cwd)
        # then the outer level repository. 
        self.deleteBranch(branch,force)

        return True
