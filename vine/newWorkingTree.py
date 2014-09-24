import os

import option
import utility
import grapeGit as git
import grapeMenu


# Create a custom sparse checkout view in a new working tree
class NewWorkingTree(option.Option):
    """
    grape cv: create a new custom view
    Usage: grape-cv [--source=<repo>] [--dest=<name>] [--destPath=<path>] [[--noSparse] | [-- <uvargs>...]]  

    Options: 
        --source=<repo>     Path to original clone. 
        --dest=<name>       Name of new workspace. 
        --destPath=<path>   Path (must exist) to place new workspace in. 
                            Full path to workspace will be <path>/<name>
        --noSparse          Skips grape uv, does a vanilla checkout instead. 
    Arguments: 
        <uvargs>            Arguments to pass to grape uv. Note that if you are using the -f
                            option, you should use an absolute path. 
    """
    def __init__(self):
        super(NewWorkingTree, self).__init__()
        self._key = "cv"
        self._section = "Workspace"

    def description(self):
        return "Create a custom sparse checkout view in a new working tree"

    def execute(self, args):
        try:
            clonePath = git.baseDir()
            if clonePath == "":
                return False
        except git.GrapeGitError:
            pass
        
        clonePath = args["--source"]
        if not clonePath: 
            clonePath = utility.userInput("Enter path to original clone", clonePath)

        newTree = args["--dest"]
        if not newTree:
            newTree = utility.userInput("Enter name of new working tree")

        newTreePath = args["--destPath"]
        if not newTreePath:
            newTreePath = utility.userInput("Enter desired location of new working tree (must exist)",
                                            os.path.realpath(os.path.join(clonePath, "../")))

        newRepo = os.path.join(newTreePath, newTree)
        #TODO: When grape is installed to PUBLIC, the first argument here should be the
        # publically available git-new-workdir, instead of the version in the local repo.
        p = utility.executeSubProcess(os.path.join(os.path.dirname(__file__), "..", "git-new-workdir")
                                      + " " + clonePath + " " + newRepo, workingDirectory=os.getcwd())
        p.wait()
        os.chdir(newRepo)
        if not args["--noSparse"]:
            print "created new working tree %s in %s. Calling grape uv from new workspace now." % (newTree, newTreePath)
            menu = grapeMenu.menu()
            return menu.applyMenuChoice('uv', ["uv"] + args["<uvargs>"])
        else:
            git.checkout("HEAD")
            return True

    def setDefaultConfig(self, config):
        pass
