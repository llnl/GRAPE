import logging
from vine import grape_errors
from vine import grapeGit as git
from vine import multi_repo_cmd_launcher
from vine import vine_logging
from vine import vine_subprocess
from vine.option import Option
from vine.vine_logging import log_wrapper


class ForEach(Option):
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


    @log_wrapper
    def execute(self,args):
        cmd = args["<cmd>"]
        retvals = multi_repo_cmd_launcher.MultiRepoCommandLauncher(foreach, runInOuter = not args["--noTopLevel"],
                                           skipSubmodules= args["--noSubmodules"],
                                           runInSubprojects= not args["--noSubprojects"], globalArgs = args).launchFromWorkspaceDir(handleMRE=handleForeachMRE)
        return retvals

    def setDefaultConfig(self,config):
        pass

def foreach(repo='', branch='', args={}):
    cmd = args["<cmd>"]
    with git.cd(repo):
        vine_subprocess.executeSubProcess(cmd, repo, verbose = -1)
    return True

def handleForeachMRE(mre):
    for e1 in mre.exceptions():
        try:
            raise e1
        except grape_errors.GrapeGitError as e:
            logging.error("Foreach failed.")
            logging.error(e.gitCommand)
            logging.error(e.cwd)
            logging.error(e.gitOutput)
            return False
