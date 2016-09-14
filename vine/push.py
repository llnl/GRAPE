import os
import option
import grapeGit as git
import utility
import grapeConfig


class Push(option.Option):
    """
    grape push pushes your current branch to origin for your outer level repo and all submodules.
    it uses 'git push -u origin HEAD' for the git command.

    Usage: grape-push [--noRecurse] 

    Options:
    --noRecurse     Don't perform pushes in submodules.  

    """
    def __init__(self):
        super(Push, self).__init__()
        self._key = "push"
        self._section = "Workspace"

    def description(self):
        return "Pushes your current branch to origin in all projects in this workspace."

    def execute(self, args):
        baseDir = utility.workspaceDir()

        cwd = os.getcwd()
        os.chdir(baseDir)
        currentBranch = git.currentBranch()
        config = grapeConfig.grapeConfig()
        publicBranches = config.getPublicBranchList()


            
        submodules = git.getActiveSubmodules()
        
        retvals = utility.MultiRepoCommandLauncher(push).launchFromWorkspaceDir(handleMRE=handlePushMRE)
        
        os.chdir(cwd)        
        utility.printMsg("Pushed current branch to origin")
        return False not in retvals
    
    def setDefaultConfig(self, config):
        pass

def push(repo='', branch='master'):
    with utility.cd(repo):
        utility.printMsg("Pushing %s in %s..." % (branch, repo))
        git.push("-u origin %s" % branch, throwOnFail=True)
        
def handlePushMRE(mre):
    for e1 in mre.exceptions():
        try:
            raise e1
        except git.GrapeGitError as e:
            utility.printMsg("Failed to push branch.")
            print e.gitCommand
            print e.cwd
            print e.gitOutput
            return False            

if __name__ is "__main__":
    import grapeMenu
    menu = grapeMenu.menu()
    menu.applyMenuChoice("push", [])
    