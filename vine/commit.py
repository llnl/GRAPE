import os
import option
import grapeGit as git
import grapeConfig
import utility

class Commit(option.Option):
    """
    Usage: grape-commit [-m <message>] [-a | <filetree>]  

    Options:
    -m <message>    The commit message.
    -a              Commit modified files that have not been staged.
    

    Arguments:
    <filetree> The relative path of files to include in this commit. 

    """
    def __init__(self):
        super(Commit,self).__init__()
        self._key = "commit"
        self._section = "Workspace"

    def description(self):
        return "runs git commit in all projects in this workspace"

    def commit(self, commitargs):
        try:
            git.commit(commitargs)
            return True
        except git.GrapeGitError as e: 
            utility.printMsg("Commit failed. Perhaps there were no staged changes? Use -a to commit all modified files.")
            return False

    def execute(self, args):
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
        subprojects = grapeConfig.GrapeConfigParser.getAllActiveNestedSubprojectPrefixes() 
        for sub in submodules +  subprojects:
            os.chdir(os.path.join(baseDir,sub))
            subStatus = git.status("--porcelain")
            if subStatus:
                utility.printMsg("Committing in %s..." % sub)
                if self.commit(commitargs): 
                    os.chdir(baseDir)
                    utility.printMsg("Staging committed change in %s..." % sub)
                    git.add(sub)
        
        os.chdir(baseDir)
        if submodules or git.status("--porcelain"): 
            utility.printMsg("Performing commit in outer level project...")
            self.commit(commitargs)
        return True
    
    def setDefaultConfig(self,config): 
       pass
    
