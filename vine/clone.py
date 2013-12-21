import os, sys
import grapeConfig
import option, utility
filedir = os.path.dirname(os.path.abspath(__file__))
grapedir = os.path.join(filedir,"..")
if not grapedir in sys.path:
    sys.path.append( grapedir )
import grapeGit as git

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
        process = utility.executeSubProcess("git clone %s %s" % (remotePath, destPath))
        if process.returncode != 0:
            print("Error: Git Clone failed.")
            return False
        print("Clone succeeded!")
        return True
