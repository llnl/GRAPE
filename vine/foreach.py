import os
import option
import grapeGit as git
import utility
import grapeConfig

class ForEach(option.Option):
    """
    Executes a command in each project in this workspace (including the outer level project). 

    Usage: grape-foreach [--quiet] [--noTopLevel] [--currentCWD] <cmd> 

    Options:
    --quiet        Quiets git's printout of "Entering submodule..."
    --noTopLevel   Does not call <cmd> in the workspace directory, only in submodules and subprojects. 
    --currentCWD   grape foreach normally starts work from the workspace top level directory. This flag 
                   starts work from the current working directory. 

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
        cwd = os.getcwd() if args["--currentCWD"] else utility.workspaceDir()
        os.chdir(cwd)
        # ensure cwd is the top level of the current git repository.
        # this will be the workspaceDir if --currentCWD was not set, or the root
        # of the project the user is in if --currentCWD is set. 
        cwd = git.baseDir()
        os.chdir(cwd)
        for sub in git.getActiveSubmodules():
            if not quiet:
                utility.printMsg("Entering %s..." % sub) 
            utility.executeSubProcess(cmd, workingDirectory=os.path.join(cwd,sub), verbose=-1)
        
        # execute in nested subprojects
        for proj in grapeConfig.GrapeConfigParser.getAllActiveNestedSubprojectPrefixes(cwd):
            if not quiet:
                utility.printMsg("Entering %s..." % proj)
            os.chdir(os.path.join(cwd, proj))
            utility.executeSubProcess(cmd, workingDirectory=os.path.join(cwd,proj), verbose=-1)
        if not args["--noTopLevel"]:
            utility.executeSubProcess(cmd,cwd)
        os.chdir(cwd)
        return True
    
    def setDefaultConfig(self,config): 
        pass
    
