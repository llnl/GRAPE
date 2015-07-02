import os
import option
import grapeGit as git
import grapeMenu
import utility
import grapeConfig
import resumable

def stashHelper(repo=".", branch=""):
    return [repo, git.stash()]
    
def popHelper(repo=".", branch=""):
    return [repo, git.stash("pop")]
    
def listHelper(repo=".", branch=""):
    return [repo, git.stash("list")]

class Stash(option.Option):
    """
    grape stash can run simple git stash, git stash pop, or git stash list commands in all repositories
    in your workspace. 
    
    Note that this is a bit scary - a simple git stash pop will attempt to apply the most recently stashed
    commit in each repo, grape makes no attempt of tracking of which commits were stashed on the most recent
    call to grape stash, so if you do a stash with active edits in one repo, then later do a stash with
    active edits in another repo, then grape stash pop will trigger pops in both repos, in a sense breaking First-In-Last-Out semantics that one might expect.

    Usage: grape-stash
           grape-stash pop
           grape-stash list

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
        elif args["list"]:
            launcher = utility.MultiRepoCommandLauncher(listHelper)
        else:
            launcher = utility.MultiRepoCommandLauncher(stashHelper)
        try:
            retvals = launcher.launchFromWorkspaceDir()
            for r in retvals:
                if r[1]:
                    print "%s: %s" % (r[0], r[1])
        except utility.MultiRepoException as mre:
            for e, r in zip(mre, mre.repos):
                print("%s:\n%s" % (r, e.gitOutput))
            
        return True
            

    def setDefaultConfig(self, config):
        pass
