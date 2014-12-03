import os
import shutil

import grapeConfig
import grapeMenu
import option
import grapeGit as git
import utility


class Checkout(option.Option):
    """
    Usage: grape-checkout  [-b] <branch> [-v]

    Options:

    -b      Create the branch off of the current HEAD in each project.
    -v      Be more verbose. 
    

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
    def handledCheckout(checkoutargs, branch, project, quiet=False):
        git.fetch(quiet=quiet)
        try:
            git.checkout(checkoutargs + ' ' + branch, quiet=quiet)
            git.pull("origin %s" % branch, quiet=quiet)
        except git.GrapeGitError as e:
            if "pathspec" in e.gitOutput:
                createNewBranch = utility.userInput("Branch not found locally or remotely. Would you like to create a "
                                                    "new branch called %s?\n(y,n)" % branch, 'y')
                if createNewBranch:
                    utility.printMsg("Creating new branch %s in %s." % (branch, project))
                    git.checkout(checkoutargs+" -b "+branch, quiet=quiet)

            elif "already exists" in e.gitOutput:
                utility.printMsg("Branch %s already exists in %s." % (branch, project))
                branchDescription = git.commitDescription(branch)
                headDescription = git.commitDescription("HEAD")
                if branchDescription == headDescription:
                    utility.printMsg("Branch %s and HEAD are the same. Switching to %s." % (branch, branch))
                    action = "k"
                else:
                    utility.printMsg("Branch %s and HEAD are not the same." % branch)
                    action = ''
                    valid = False
                    while not valid:
                        action = utility.userInput("Would you like to \n (k)eep it as is at: %s \n"
                                                   " or \n (f)orce it to: %s? \n(k,f)" %
                                                   (branchDescription, headDescription), 'k')
                        valid = (action == 'k') or (action == 'f')
                        if not valid:
                            utility.printMsg("Invalid input. Enter k or f. ")
                if action == 'k':
                    git.checkout(branch, quiet=quiet)
                elif action == 'f':
                    git.checkout("-B %s" % branch, quiet=quiet)
            elif "conflict" in e.gitOutput.lower(): 
                utility.printMsg("CONFLICT occurred when pulling %s from origin." % branch)
            elif "does not appear to be a git repository" in e.gitOutput.lower():
                utility.printMsg("Remote 'origin' does not exist. "
                                 "This branch was not updated from a remote repository.")
            elif "Couldn't find remote ref" in e.gitOutput:
                utility.printMsg("Remote does not have reference to %s. You may want to push this branch. " % branch)
            else:
                raise e

    @staticmethod
    def parseGitModulesDiffOutput(output, addedModules, removedModules):
        print output.split('\n')
        for line in output.split('\n'):
            if "+[submodule" in line:
                print line
                print line.split('"')
                addedModules.append(line.split('"')[1])
            if "-[submodule" in line:
                removedModules.append(line.split('"')[1])

        return addedModules, removedModules

    def execute(self, args):
        quiet = not args["-v"]
        checkoutargs = ''
        branch = args["<branch>"]
        if args['-b']: 
            checkoutargs += " -b"

        workspaceDir = utility.workspaceDir()
        os.chdir(workspaceDir)
        currentSHA = git.shortSHA("HEAD")

        utility.printMsg("Performing checkout in outer level project.")
        self.handledCheckout(checkoutargs, branch, git.baseDir(), quiet=quiet)
        previousSHA = currentSHA

        submoduleListDidChange = ".gitmodules" in git.diff("--name-only %s %s" % (previousSHA, branch), quiet=quiet)
        addedModules = []
        removedModules = []
        uvArgs = []
        if submoduleListDidChange and grapeConfig.grapeConfig().getboolean("workspace", "manageSubmodules"):

            self.parseGitModulesDiffOutput(git.diff("%s %s --no-ext-diff -- .gitmodules" % (previousSHA, branch)), addedModules,
                                           removedModules)
            if not addedModules and not removedModules:
                uvArgs.append("--checkSubprojects")

            if removedModules:
                for sub in removedModules:
                    try:
                       os.chdir(os.path.join(workspaceDir, sub))
                       if git.isWorkingDirectoryClean():
                           clean = utility.userInput("Would you like to remove the submodule %s ?" % sub, 'n')
                           if clean:
                               utility.printMsg("Removing clean submodule %s." % sub)
                               os.chdir(workspaceDir)
                               shutil.rmtree(os.path.join(workspaceDir, sub))
                       else:
                           utility.printMsg("Unstaged / committed changes in %s, not removing." % sub)
                           os.chdir(workspaceDir)
                    except OSError:
                       pass
            if addedModules:
                utility.printMsg("New submodules %s are on branch %s. Updating view ..." % (addedModules, branch))
        else:
            uvArgs.append("--checkSubprojects")

        if not quiet:
            uvArgs.append("-v")
            
        if args["-b"]: 
            uvArgs.append("-b")
        
        utility.printMsg("Calling grape uv %s to ensure branches are consistent across all subprojects and submodules." % ' '.join(uvArgs))
        grapeMenu.menu().applyMenuChoice('uv', uvArgs)

        os.chdir(workspaceDir)
        
        utility.printMsg("Switched to %s." % branch)
        return True
    
    def setDefaultConfig(self, config):
        pass
