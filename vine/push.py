import os
import option
import grapeGit as git
import utility


class Push(option.Option):
    """
    grape push pushes your current branch to origin for your outer level repo and all submodules.
    it uses 'git push -u origin HEAD' for the git command.

    Usage: grape-push [--norecurse] [-v]

    Options:
    --norecurse     Don't perform pushes in submodules.  
    -v              Show more git output. 

    """
    def __init__(self):
        super(Push, self).__init__()
        self._key = "push"
        self._section = "Workspace"

    def description(self):
        return "Pushes your current branch to origin in all projects in this workspace."

    def execute(self, args):
        quiet = not args["-v"]
        baseDir = utility.workspaceDir()
        pushargs = "-u origin HEAD"
        cwd = os.getcwd()
        os.chdir(baseDir)
        submodules = git.getActiveSubmodules()
        
        print("GRAPE: Performing push in outer level project")
        git.push(pushargs, quiet=quiet)
        if submodules:
            print("GRAPE: Performing pushes in all submodules")
        for sub in submodules: 
            os.chdir(os.path.join(baseDir, sub))
            git.push(pushargs, quiet=quiet)
        os.chdir(cwd)
        
        print("GRAPE: pushed current branch to origin")
        return True
    
    def setDefaultConfig(self, config):
       pass