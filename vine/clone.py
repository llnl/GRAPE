import os, sys
from grapeConfig import grapeConfig
import option, utility
if not ".." in sys.path:
    sys.path.append( ".." )
import git

class Clone(option.Option):
    def __init__(self):
        self._key = "clone"
        self._section = "Getting Started"

    """Clones the ALE3D repo into a new local repo"""
    def description(self):
        name = grapeConfig().get("repo","name")
        return "Clone the %s repo and initialize your git config" % name

    def execute(self):
        user = utility.getUserName()

        remotePath = utility.userInput("Enter Remote Repo address:",
                               ("https://%s@rzlc.llnl.gov/stash/scm/ale/ale3d.git" % user))

        destPath = utility.userInput("Enter destination directory:", os.path.join(os.getcwd(), "ale3d"))

        print("calling git clone %s %s" % (remotePath,destPath))
        print("you may need to authenticate using your CRYPTOCARD")
        repo = git.Repo(destPath)
        try:
            repo = repo.clone(remotePath)
        except git.GitCommandError as error:
            print("Error: %s: git clone failed", remotePath)
            print(error)
            return False

        return True
