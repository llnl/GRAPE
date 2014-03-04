import sys
import option
import grapeGit as git
import utility

class Walkthrough(option.Option):
    """ 
    grape w(alkthrough)
    Usage: grape-w [--b1=<branch> [--b2=<branch>]] [<filetree-ish>] [--nogui]

    Options:
        --b1=<branch>   The branch to compare the current branch to. 
        --b2=<branch>   The branch to compare against b1. [default: HEAD]
        --nogui         Don't use kompare to do the walkthrough. 

    Optional Arguments:
        <filetree-ish>  The files to compare.  

    """
    def __init__(self):
        self._key = "w"
        self._section = "Code Reviews"

    def description(self):
        return "Walk through diffs between branches"

    def execute(self,args):
        b1 =  args["--b1"]
        if not b1: 
            b1 = utility.userInput("Enter name of branch to compare","develop")
        b2 = args["--b2"]
       

        # may want to exit out of diffs early, need to make sure to pass the
        # signal down
        files = args["<filetree-ish>"]
        if (not files): 
            files = ""
        try:
            print("diffing files. Use Ctrl-C to stop.")
            p = git.diff("%s %s %s" % (b1,b2,files))
        except:
            pass
        return True

