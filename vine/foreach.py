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
        cmd = args["<cmd>"]
        retvals = utility.MultiRepoCommandLauncher(foreach, runInOuter = not args["--noTopLevel"], 
                                                   skipSubmodules= args["--noSubmodules"], 
                                                   runInSubprojects= not args["--noSubprojects"], globalArgs = args).launchFromWorkspaceDir(handleMRE=handleForeachMRE)
        return retvals

    def setDefaultConfig(self,config): 
        pass

def foreach(repo='', branch='', args={}):
    cmd = args["<cmd>"]
    with utility.cd(repo): 
        utility.executeSubProcess(cmd, repo, verbose = -1)
    return True            

def handleForeachMRE(mre):
    for e1 in mre.exceptions():
        try:
            raise e1
        except git.GrapeGitError as e:
            utility.printMsg("Foreach failed.")
            print e.gitCommand
            print e.cwd
            print e.gitOutput
            return False            

    
