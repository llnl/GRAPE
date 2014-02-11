import os, sys
import grapeConfig
import option, utility
import grapeGit as git
class Clone(option.Option):
    """ grape-clone
    Clones a git repo and configures it for use with git.

    Usage: grape-clone <url> <path> [--recursive]

    Arguments:
        <url>       The URL of the remote repository 
        <path>      The directory where you want to clone the repo to. 

    Options:
        --recursive   Recursively clone submodules. 
    """

    def __init__(self):
        self._key = "clone"
        self._section = "Getting Started"

    #Clones the default repo into a new local repo
    def description(self):
        name = grapeConfig.grapeConfig().get("repo","name")
        return "Clone a repo and configure it for grape" 

    def execute(self,args):
        remotePath = args["<url>"]
        destPath = args["<path>"]
        rStr = "--recursive" if args["--recursive"] else ""

        git.gitcmd("clone %s %s %s" % (rStr,remotePath, destPath), "Error: Git Clone failed.")
        print("Clone succeeded!")
        os.chdir(destPath)
        grapecmd = os.path.join(os.path.dirname(__file__),"..","grape")
        utility.executeSubProcess("%s config" % grapecmd)
        return True
