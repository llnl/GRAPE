import os
import option
import grapeGit as git
import utility

class ForEach(option.Option):
    """
    Executes a command in each project in this workspace (including the outer level project). 

    Usage: grape-foreach [--quiet] <cmd> 

    Options:
    --quiet      Quiets git's printout of "Entering submodule..."

    Arguments:
    <cmd>        The cmd to execute. 

    """
    def __init__(self):
        self._key = "foreach"
        self._section = "Workspace"

    def description(self):
        return "runs a command in all projects in this workspace"


    def execute(self,args):
        quiet = args["--quiet"]
        quiet = "--quiet" if quiet else ""
        cmd = args["<cmd>"]

        foreachcmd = "%s %s" % (quiet,cmd)
        cwd = utility.workspaceDir()
        os.chdir(cwd)
        git.submodule("foreach %s %s" % (quiet,cmd))
        utility.executeSubProcess(cmd,cwd,verbose = 0 if quiet else 2)
        return True
    
    def setDefaultConfig(self,config): 
       pass
    
