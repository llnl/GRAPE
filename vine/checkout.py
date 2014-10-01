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
        super(Checkout, self).__init__()
        self._key = "checkout"
        self._section = "Workspace"

    def description(self):
        return "Checks out a branch in all projects in this workspace."

    @staticmethod
    def handledCheckout(checkoutargs, branch, project, quiet=True):
        git.fetch(quiet=False)
        try:
            git.checkout(checkoutargs + ' ' + branch, quiet=False)
            git.pull("origin %s" % (branch))
        except git.GrapeGitError as e:
            if "pathspec" in e.gitOutput:
                utility.printMsg("creating new branch %s in %s" % (branch, project))
                git.checkout(checkoutargs+" -b "+branch, quiet=False)
            elif "already exists" in e.gitOutput:
                utility.printMsg("branch %s already exists in %s" % (branch, project))
                branchDescription = git.commitDescription(branch)
                headDescription = git.commitDescription("HEAD")
                if branchDescription == headDescription:
                    utility.printMsg("branch %s and HEAD are the same. Switching to %s" % (branch, branch))
                    action = "k"
                else:
                    action = ''
                    valid = False
                    while not valid:
                        action = utility.userInput("Would you like to \n (k)eep it as is at: %s \n"
                                                   " or \n (f)orce it to: %s? \n(k,f)" %
                                                   (branchDescription, headDescription), 'k')
                        valid = (action == 'k') or (action == 'f')
                        if not valid:
                            print "Invalid input. Enter k or f. "
                if action == 'k':
                    git.checkout(branch, quiet=False)
                elif action == 'f':
                    git.checkout("-B %s" % branch, quiet=False)
            elif "conflict" in e.gitOuput.lower(): 
                utility.printMsg("CONFLICT occurred when pulling %s from origin" % branch)
            elif "does not appear to be a git repository" in e.gitOutput.lower():
                utility.printMsg("Remote 'origin' does not exist. This branch was not updated from a remote repository.")



    def execute(self, args):
        quiet = not args["-v"]
        checkoutargs = ''
        branch = args["<branch>"]
        if args['-b']: 
            checkoutargs += " -b"

        baseDir = utility.workspaceDir()
        os.chdir(baseDir)
        submodules = git.getActiveSubmodules()
        
        print("GRAPE: Performing checkout in outer level project")
        self.handledCheckout(checkoutargs, branch, git.baseDir(), quiet=quiet)

        if submodules:
            print("GRAPE: Performing checkouts in all active submodules")
            git.submodule("update", quiet=quiet)
        for sub in submodules:
            utility.printMsg("Performing checkout in %s" % sub)
            os.chdir(os.path.join(baseDir, sub))
            self.handledCheckout(checkoutargs, branch, sub, quiet=quiet)

        os.chdir(baseDir)
        
        print("GRAPE: Switched to %s" % branch)
        return True
    
    def setDefaultConfig(self, config):
       pass
