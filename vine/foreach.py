import os
import option
import grapeGit as git
import utility
import grapeConfig

class ForEach(option.Option):
    """
    Executes a command in each project in this workspace (including the outer level project). 

    Usage: grape-foreach [--quiet] [--noTopLevel] <cmd> 

    Options:
    --quiet        Quiets git's printout of "Entering submodule..."
    --noTopLevel   Does not call <cmd> in the workspace directory, only in submodules and subprojects. 

    Arguments:
    <cmd>        The cmd to execute. 

    """
    def __init__(self):
        super(ForEach, self).__init__()
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
        
        # execute in nested subprojects
        for proj in grapeConfig.GrapeConfigParser.getAllActiveNestedSubprojectPrefixes(): 
            os.chdir(os.path.join(cwd, proj))
            utility.executeSubProcess(cmd, workingDirectory=os.path.join(cwd,proj), 
                                      verbose=0 if quiet else 2)
        if not args["--noTopLevel"]:
            utility.executeSubProcess(cmd,cwd,verbose = 0 if quiet else 2)
        
        return True
    
    def setDefaultConfig(self,config): 
       pass
    
