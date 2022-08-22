import logging
from vine import grape_errors
from vine import multi_repo_cmd_launcher
from vine import vine_logging
from vine import vine_subprocess
from vine.workspace_dir_handler import WorkspaceDirHandler
from vine.option import Option
from vine.vine_logging import log_wrapper


class ForEach(Option, WorkspaceDirHandler):
    """
    Executes a command in the top level project, each submodule, and each nested subproject in this workspace.

    Usage: grape-foreach [--noTopLevel] [--noSubprojects] [--noSubmodules] [--currentCWD] <cmd>

    Options:
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
        launcher = multi_repo_cmd_launcher.MultiRepoCommandLauncher(
            foreach, runInOuter=not args["--noTopLevel"],
            skipSubmodules=args["--noSubmodules"],
            runInSubprojects=not args["--noSubprojects"],
            globalArgs=args,
            workspace_dir=self.workspace_dir)
        retvals = launcher.launchFromWorkspaceDir(handleMRE=handleForeachMRE)
        return False not in retvals

    def setDefaultConfig(self,config):
        pass

def foreach(repo='', branch='', args={}, *, workspace_dir):
    cmd = args["<cmd>"]
    completed_process = vine_subprocess.executeSubProcess(cmd, working_dir=repo)
    return completed_process.returncode == 0

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
        except FileNotFoundError as e:
            logging.warning("File not found - perhaps .grapeuserconfig is out of date?")
            logging.warning(e)
            return True
