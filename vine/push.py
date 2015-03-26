import os
import option
import grapeGit as git
import utility
import grapeConfig


class Push(option.Option):
    """
    grape push pushes your current branch to origin for your outer level repo and all submodules.
    it uses 'git push -u origin HEAD' for the git command.

    Usage: grape-push [--norecurse] 

    Options:
    --norecurse     Don't perform pushes in submodules.  

    """
    def __init__(self):
        super(Push, self).__init__()
        self._key = "push"
        self._section = "Workspace"

    def description(self):
        return "Pushes your current branch to origin in all projects in this workspace."

    def execute(self, args):
        baseDir = utility.workspaceDir()
        pushargs = "-u origin HEAD"
        cwd = os.getcwd()
        os.chdir(baseDir)
        submodules = git.getActiveSubmodules()
        
        utility.printMsg("Performing push in outer level project")
        try:
            git.push(pushargs, throwOnFail=True)
            if submodules:
                utility.printMsg("Performing pushes in all active submodules")
            for sub in submodules: 
                os.chdir(os.path.join(baseDir, sub))
                utility.printMsg("Pushing in %s..." % sub)
                git.push(pushargs)
    
            nestedSubprojects = grapeConfig.GrapeConfigParser.getAllActiveNestedSubprojectPrefixes(baseDir)
            if nestedSubprojects:
                utility.printMsg("Performing pushes in all active subprojects")
            for proj in nestedSubprojects:
                os.chdir(os.path.join(baseDir, proj))
                utility.printMsg("Pushing in %s..." % proj)
                git.push(pushargs)
        except git.GrapeGitError as e:
            utility.printMsg("Failed to push branch.")
            print e.gitCommand
            print e.cwd
            print e.gitOutput
            return False
        os.chdir(cwd)
        
        utility.printMsg("Pushed current branch to origin")
        return True
    
    def setDefaultConfig(self, config):
       pass
