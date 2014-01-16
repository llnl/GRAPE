import os, sys
import grapeConfig
import option, utility
filedir = os.path.dirname(os.path.abspath(__file__))
grapedir = os.path.join(filedir,"..")
if not grapedir in sys.path:
    sys.path.append( grapedir )
import grapeGit as git

class DeleteBranch(option.Option):
    def __init__(self):
        self._key = "db"
        self._section = "Gitflow Tasks"

    """ Deletes a branch both here and on the remote. """
    def description(self):
        return "Delete a branch on both your local repo and on origin"

    def execute(self,args=None):
        branch = None
        if (args): 
            branch = args[0]
        else:
            branch = utility.userInput("Enter name of branch to delete")
                               
        git.branch("-d %s" % branch)
        git.push("--delete %s" % branch)
        return True
