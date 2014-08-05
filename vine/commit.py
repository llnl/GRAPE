import os
import option
import grapeGit as git
import utility

class Commit(option.Option):
    """
    Usage: grape-commit [-v] [-m <message>] [-a | <filetree>]  

    Options:
    -m <message>    The commit message.
    -v              Show git commands being issued.
    -a              Commit modified files that have not been staged.
    

    Arguments:
    <filetree> The relative path of files to include in this commit. 

    """
    def __init__(self):
        self._key = "commit"
        self._section = "Workspace"

    def description(self):
        return "runs git commit in all projects in this workspace"

    def commit(self, commitargs):
        try:
            git.commit(commitargs)
        except git.GrapeGitError as e: 
            print("commit failed. Perhaps there were no staged changes? Use -a to commit all modified files.")

    def execute(self, args):
        quiet = not args["-v"]
        commitargs = ""
        if args['-a']: 
            commitargs = commitargs +  " -a"
        elif args["<filetree>"]:
            commitargs = commitargs + " %s"% args["<filetree>"]
        if not args['-m']:
            args["-m"] = utility.userInput("Please enter commit message:")
        commitargs += " -m \"%s\"" % args["-m"]
         
        baseDir = utility.workspaceDir()
        os.chdir(baseDir)

        submodules = git.getModifiedSubmodules()
        for file in submodules:
            os.chdir(os.path.join(baseDir,file))
            subStatus = git.status("--porcelain", quiet=quiet)
            if subStatus:
                self.commit(commitargs)
            print(' ')
        os.chdir(baseDir)
        print("GRAPE: Performing commit in outer level project")
        self.commit(commitargs)
        return True
    
    def setDefaultConfig(self,config): 
       pass
    
