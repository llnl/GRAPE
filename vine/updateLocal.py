import logging
import os
from vine import config_parser_global
from vine import grape_errors
from vine import grapeGit as git
from vine import multi_repo_cmd_launcher
from vine.workspace_dir_handler import WorkspaceDirHandler
from vine.option import Option
from vine.vine_logging import log_wrapper


# update the repo from the remote
class UpdateLocal(Option, WorkspaceDirHandler):
    """
    grape up
    Updates the current branch and any public branches.
    Usage: grape-up [--public=<branch> ]
                    [--recurse | --noRecurse [--recurseSubprojects]]
                    [--wd=<working dir>]


    Options:
    --public=<branch>       The public branches to update in addition to the current one,
                            e.g. --public="master develop"
                            [default: .grapeconfig.flow.publicBranches ]
    --recurse               Update branches in submodules and nested subprojects.
    --noRecurse             Do not update branches in submodules and nested subprojects.
    --wd=<working dir>      Working directory which should be updated.
                            Top level workspace will be updated if this is unspecified.
    --recurseSubprojects    Recurse in nested subprojects even if you're not recursing in submodules.


    """
    def __init__(self):
        super(UpdateLocal, self).__init__()
        self._key = "up"
        self._section = "Gitflow Tasks"

    def description(self):
        return "Update local branches that are tracked in your remote repo"

    @log_wrapper
    def execute(self, args):
        if args["--wd"]:
            workspace_dir = os.path.abspath(args["--wd"])
        else:
            workspace_dir = self.workspace_dir

        config = config_parser_global.grapeConfig()
        recurseSubmodules = config.getboolean(self.SECTION_WORKSPACE, "manageSubmodules") or args["--recurse"]
        skipSubmodules = args["--noRecurse"]

        recurseNestedSubprojects = not args["--noRecurse"] or args["--recurseSubprojects"]
        publicBranches = [x.strip() for x in args["--public"].split()]
        launchers = []
        for branch in publicBranches:
            new_launcher = multi_repo_cmd_launcher.MultiRepoCommandLauncher(
                fetchLocal, runInSubmodules=recurseSubmodules,
                runInSubprojects=recurseNestedSubprojects, branch=branch,
                listOfRepoBranchArgTuples=None, skipSubmodules=skipSubmodules,
                outer=workspace_dir, execution_path=workspace_dir)
            launchers.append(new_launcher)
        if launchers:
            launcher = launchers[0]
            for l in launchers[1:]:
                launcher.MergeLaunchSet(l)
            launcher.collapseLaunchSetBranches()
            launcher.launchFromWorkspaceDir(handleMRE=fetchLocalHandler)

        return True

    def setDefaultConfig(self, config):
        pass

def fetchLocalHandler(mre):
    for e in mre.exceptions():
        logging.error(repr(e.gitOutput))
    raise mre

def fetchLocal(repo='unknown', branch=[], *, workspace_dir):
    # the execution path we actually care about is in repo
    execution_path = repo
    # branch is actually the list of branches
    branches = branch
    if not branches:
        return

    currentBranch = git.currentBranch(execution_path=execution_path)

    git.fetch("--prune", execution_path=execution_path)
    git.fetch("--tags --force", execution_path=execution_path)
    allRemoteBranches = git.remoteBranches(execution_path=execution_path)
    fetchArgs = "origin "
    toFetch = []
    for b in branches:
        if b != currentBranch:
            if git.join_list_as_git_path(['origin', b]) in allRemoteBranches:
                fetchArgs += f"{b}:{b} "
                toFetch.append(b)
        else:
            try:
                logging.info(
                    f"Pulling current branch {currentBranch} in {execution_path}")
                git.pull(f"origin {currentBranch}", execution_path=execution_path)
            except grape_errors.GrapeGitError:
                logging.error(f"GRAPE: Could not pull {currentBranch} from" +
                              " origin. Maybe you haven't pushed it yet?")
    try:
        if toFetch:
            logging.info(f"updating {','.join(toFetch)} in {execution_path}")
            git.fetch(fetchArgs, execution_path=execution_path)
    except grape_errors.GrapeGitError as e:
        # let non-fast-forward fetches slide
        if "rejected" in e.gitOutput.lower() and "non-fast-forward" in e.gitOutput.lower():
            logging.error(e.gitCommand)
            logging.error(e.gitOutput)
            logging.warning("GRAPE: WARNING: one of your public branches" +
                            f" {','.join(branches)} in {execution_path} has local " +
                            "commits! Did you forget to create a topic " +
                            "branch?")
        elif "refusing to fetch into current branch" in e.gitOutput.lower():
            logging.error(e.gitOutput)
        else:
            raise e
