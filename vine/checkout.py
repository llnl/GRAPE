import os
import option
import grapeGit as git
import utility

class Checkout(option.Option):
    """
    Usage: grape-checkout [-v] [-b] <branch> 

    Options:
    -v      Show git commands being issued. 
    -b      Create the branch off of the current HEAD in each project.
    

    Arguments:
    <branch>    The name of the branch to checkout. 

    """
    def __init__(self):
        self._key = "checkout"
        self._section = "Workspace"

    def description(self):
        return "Checks out a branch in all projects in this workspace."


    def execute(self,args):
        quiet = not args["-v"]
        checkoutargs = ''
        if args['-b']: 
            checkoutargs = checkoutargs +  " -b"
        checkoutargs = checkoutargs + " %s"% args["<branch>"]
        baseDir =  utility.workspaceDir()
        os.chdir(baseDir)
        submodules = git.getActiveSubmodules()
        
        print("GRAPE: Performing checkout in outer level project")
        git.checkout(checkoutargs,quiet=quiet)
        if submodules:
            print("GRAPE: Performing checkouts in all submodules")
        for sub in submodules: 
            os.chdir(os.path.join(baseDir,sub))
            git.checkout(checkoutargs,quiet = quiet)
        os.chdir(baseDir)
        
        print("GRAPE: Switched to %s" % args["<branch>"])
        return True
    
    def setDefaultConfig(self,config): 
       pass
    
