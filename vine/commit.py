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

    def commit(self, commitargs, repo):
        try:
            git.commit(commitargs)
            return True
        except git.GrapeGitError as e: 
            utility.printMsg("Commit in %s failed. Perhaps there were no staged changes? Use -a to commit all modified files." % repo)
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
         
        wsDir = utility.workspaceDir()
        os.chdir(wsDir)

        submodules = [(True, x ) for x in git.getModifiedSubmodules()]
        subprojects = [(False, x) for x in grapeConfig.GrapeConfigParser.getAllActiveNestedSubprojectPrefixes()]
        for stage,sub in submodules +  subprojects:
            os.chdir(os.path.join(wsDir,sub))
            subStatus = git.status("--porcelain -uno")
            if subStatus:
                utility.printMsg("Committing in %s..." % sub)
                if self.commit(commitargs, sub) and stage: 
                    os.chdir(wsDir)
                    utility.printMsg("Staging committed change in %s..." % sub)
                    git.add(sub)
        
        os.chdir(wsDir)
        if submodules or git.status("--porcelain"): 
            utility.printMsg("Performing commit in outer level project...")
            self.commit(commitargs, wsDir)
        return True
    
    def setDefaultConfig(self,config): 
        pass
