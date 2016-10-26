import os
import option
import grapeGit as git
import utility
import grapeConfig

class ForEach(option.Option):
    """
    Executes a command in the top level project, each submodule, and each nested subproject in this workspace.

    Usage: grape-foreach [--quiet] [--noTopLevel] [--noSubprojects] [--noSubmodules] [--currentCWD] <cmd> 

    Options:
    --quiet          Quiets git's printout of "Entering submodule..."
    --noTopLevel     Does not call <cmd> in the workspace directory.
    --noSubprojects  Does not call <cmd> in any grape nested subprojects.
    --noSubmodules   Does not call <cmd> in any git submodules. 
    --currentCWD     grape foreach normally starts work from the workspace top level directory. This flag 
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

        # put in arguments 
        retvals = utility.MultiRepoCommandLauncher(foreach(cmd, cwd), runInOuter = not args["--noTopLevel"], 
                                                   skipSubmodules= args["--noSubmodules"], 
                                                   runInSubprojects= not args["--noSubprojects"]).launchFromWorkspaceDir()
        return retvals

    def setDefaultConfig(self,config): 
        pass

def foreach(cmd, cwd):
    utility.executeSubProcess(cmd, cwd, verbose = -1)
    return True            

