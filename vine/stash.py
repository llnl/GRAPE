import os
import option
import grapeGit as git
import grapeMenu
import utility
import grapeConfig
import resumable

def stashHelper():
    git.stash()
    
def popHelper():
    git.stash("pop")

class Stash(option.Option):
    """
    grape stash simply applies a git stash command to all projects in a workspace, and outputs any output that git provides.
    Note that this is a bit scary - a simple git stash pop will attempt to apply the most recently stashed commit in each repo,
    grape has no independent tracking of which commits were stashed on the most recent call to grape stash. 
    Usage: grape-stash [pop]

    Options:
    pop    Do a pop instead of a stash. 


    """
    def __init__(self):
        super(Stash, self).__init__()
        self._key = "stash"
        self._section = "Workspace"

    def description(self):
        return "Runs git stash in all repos in your workspace."

    def execute(self, args):
        
        if args["pop"]:
            launcher = utility.MultiRepoCommandLauncher(popHelper)
        else:
            launcher = utility.MultiRepoCommandLauncher(stashHelper)
        try:
            launcher.launchFromWorkspaceDir()
        except utility.MultiRepoException as mre:
            for e, r in zip(mre, mre.repos):
                print("%s:\n%s" % (r, e.gitOutput))
            
        return True
            

    def setDefaultConfig(self, config):
        pass
