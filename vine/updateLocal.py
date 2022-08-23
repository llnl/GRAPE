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
    Usage: grape-up [--public=<branch> ] [--force]
                    [--recurse | --noRecurse [--recurseSubprojects]]
                    [--wd=<working dir>]
                    [--noTopLevel]


    Options:
    --public=<branch>       The public branches to update in addition to the current one,
                            e.g. --public="master develop"
                            [default: .grapeconfig.flow.publicBranches ]
    --force                 Force update of public branches.
    --recurse               Update branches in submodules and nested subprojects.
    --noRecurse             Do not update branches in submodules and nested subprojects.
    --wd=<working dir>      Working directory which should be updated.
                            Top level workspace will be updated if this is unspecified.
    --recurseSubprojects    Recurse in nested subprojects even if you're not recursing in submodules.
    --noTopLevel            Do nothing in the top level repo.


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
        runInOuter=True
        if "--noTopLevel" in args and args["--noTopLevel"]:
            runInOuter = False
        for branch in publicBranches:
            new_launcher = multi_repo_cmd_launcher.MultiRepoCommandLauncher(
                fetchLocal, runInSubmodules=recurseSubmodules,
                runInSubprojects=recurseNestedSubprojects,
                runInOuter=runInOuter, branch=branch,
                listOfRepoBranchArgTuples=None, skipSubmodules=skipSubmodules,
                globalArgs=args,
                outer=workspace_dir, workspace_dir=workspace_dir)
            launchers.append(new_launcher)
        if launchers:
            launcher = launchers[0]
            for l in launchers[1:]:
                launcher.MergeLaunchSet(l)
            launcher.collapseLaunchSetBranches()
            retvals = launcher.launchFromWorkspaceDir(handleMRE=fetchLocalHandler)
            for retval in retvals:
                if isinstance(retval, grape_errors.GrapeGitError):
                    #return False
                    pass

        return True

    def setDefaultConfig(self, config):
        pass

def fetchLocalHandler(mre):
    for e in mre.exceptions():
        logging.error(repr(e.gitOutput))
    raise mre

def fetchLocal(repo='unknown', branch=[], args={}, *, workspace_dir):
    # the execution path we actually care about is in repo
    execution_path = repo
    # branch is actually the list of branches
    branches = branch
    if not branches:
        logging.error("branches not specified")
        return False

    currentBranch = git.currentBranch(execution_path=execution_path)

    allRemoteBranches = git.remoteBranches(execution_path=execution_path)
    fetchArgs = "--recurse-submodules=no --prune origin '+refs/tags/*:refs/tags/*' 'refs/heads/*:refs/remotes/origin/*' "
    mergeRequired = False
    for b in branches:
        if git.join_list_as_git_path(['origin', b]) in allRemoteBranches:
            if args["--force"]:
                fetchArgs += "+"
            if b == currentBranch:
                mergeRequired = True
                fetchArgs += f"{b} "
            else:
                fetchArgs += f"{b}:{b} "
    try:
        logging.debug(f"running \n\tgit fetch {fetchArgs}\n in {execution_path}")
        git.fetch(fetchArgs, execution_path=execution_path, raiseOnCommError=True)
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
            logging.error(f"GRAPE: ERROR: {execution_path}:\n{e.gitOutput}")
        else:
            raise e
    if mergeRequired:
        try:
            logging.debug( f"Merging origin/{currentBranch} into {currentBranch} in {execution_path}")
            git.merge(f"origin/{currentBranch}", execution_path=execution_path)
        except grape_errors.GrapeGitError as e:
            logging.error(f"GRAPE: Could not merge origin/{currentBranch} into {currentBranch} after fetch.")
            return False

    return True
