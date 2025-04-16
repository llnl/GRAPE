import logging
import os
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

    Usage: grape-foreach [-v] [--noTopLevel] [--noSubprojects] [--noSubmodules] [--currentCWD] [--ignoreReturnCode] <cmd>

    Options:
    -v                  Echo output from each command.
    --noTopLevel        Does not call <cmd> in the workspace directory.
    --noSubprojects     Does not call <cmd> in any grape nested subprojects.
    --noSubmodules      Does not call <cmd> in any git submodules.
    --currentCWD        grape foreach normally starts work from the workspace top level directory. This flag
                        starts work from the current working directory.
    --ignoreReturnCode  Ignore return code from <cmd>. Otherwise, returns 0 if all commands succeeded, 1 otherwise.

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
        if args["-v"]:
            logging.info(f"Executed in {len(retvals)} repos: {cmd}")
        for retval in retvals:
            if isinstance(retval, grape_errors.GrapeGitError):
                return False
        return True

    def setDefaultConfig(self,config):
        pass

def foreach(repo='', branch='', args={}, *, workspace_dir):
    cmd = args["<cmd>"]
    completed_process = vine_subprocess.executeSubProcess(cmd, working_dir=repo)
    error_return = (not args["--ignoreReturnCode"] and completed_process.returncode != 0)
    if error_return or args["-v"]:
        stdout_output = completed_process.stdout.decode()
        stderr_output = completed_process.stderr.decode()
        process_output = '\n'.join([stdout_output, stderr_output]).strip()
        if error_return:
            raise grape_errors.GrapeGitError(
                f"Error: foreach failed in {repo}", completed_process.returncode, process_output,
                cmd, cwd=repo)
        elif process_output:
            logging.info(f"[{os.path.relpath(repo, workspace_dir)}]\n{process_output}")

def handleForeachMRE(mre):
    for e1 in mre.exceptions():
        try:
            raise e1
        except grape_errors.GrapeGitError as e:
            logging.warning(f"GRAPE: Foreach failed in {e.cwd}.")
            logging.warning(f"GRAPE: Command `{e.gitCommand}' with the following output:")
            logging.warning(e.gitOutput)
            logging.warning(f"GRAPE: exited with error code {e.code}.")
        except FileNotFoundError as e:
            logging.warning("File not found - perhaps .grapeuserconfig is out of date?")
            logging.warning(e)
