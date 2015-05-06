import os
import option
import grapeGit as git
import utility
import grapeConfig


def pull(branch="develop", repo=".", rebase=False):
    if rebase:
        argStr = "--rebase origin %s" % branch
    else:
        argStr = "origin %s " % branch
    
    utility.printMsg("Pulling %s in %s..." % (branch, repo))
    git.pull(argStr, throwOnFail=True)


class Pull(option.Option):
    """
    grape pull pulls any updates to your current branch into for your outer level repo and all subprojects.
    it uses 'git pull origin <currentBranch>' for the git command.

    Usage: grape-pull [--noRecurse] [--rebase] 

    Options:
    --noRecurse     Don't perform pulls in submodules or subprojects.   
    --rebase        Rebase local changes onto remote changes instead of merging remote changes into local changes.

    """
    def __init__(self):
        super(Pull, self).__init__()
        self._key = "pull"
        self._section = "Workspace"

    def description(self):
        return "Pulls your current branch to origin in all projects in this workspace."

    def execute(self, args):
        baseDir = utility.workspaceDir()

        cwd = os.getcwd()
        os.chdir(baseDir)
        currentBranch = git.currentBranch()
        config = grapeConfig.grapeConfig()
        publicBranches = config.getPublicBranchList()


            
        submodules = git.getActiveSubmodules()
        

        try:
            launcher = utility.MultiRepoCommandLauncher(pull)
            launcher.launchFromWorkspaceDir()
                    
        except git.GrapeGitError as e:
            utility.printMsg("Failed to pull branch.")
            print e.gitCommand
            print e.cwd
            print e.gitOutput
            return False
        finally:
            os.chdir(cwd)
        
        utility.printMsg("Pulled current branch from origin")
        return True
    
    def setDefaultConfig(self, config):
        pass
