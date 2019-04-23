import os
from grape.vine import config_parser_global
from grape.vine import grape_errors
from grape.vine import grapeGit as git
from grape.vine import multi_repo_cmd_launcher
from grape.vine import utility
from grape.vine import vine_logging
from grape.vine.option import Option


# update the repo from the remote using the PyGitUp module
class UpdateLocal(Option):
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

    def execute(self, args):
        wsDir = args["--wd"] if args["--wd"] else utility.workspaceDir()
        wsDir = os.path.abspath(wsDir)
        os.chdir(wsDir)
        cwd = os.getcwd()

        config = config_parser_global.grapeConfig()
        recurseSubmodules = config.getboolean(self.SECTION_WORKSPACE, "manageSubmodules") or args["--recurse"]
        skipSubmodules = args["--noRecurse"]


        recurseNestedSubprojects = not args["--noRecurse"] or args["--recurseSubprojects"]
        publicBranches = [x.strip() for x in args["--public"].split()]
        launchers = []
        for branch in publicBranches:
            launchers.append(multi_repo_cmd_launcher.MultiRepoCommandLauncher(fetchLocal,
                                                      runInSubmodules=recurseSubmodules,
                                                      runInSubprojects=recurseNestedSubprojects,
                                                      branch=branch,
                                                      listOfRepoBranchArgTuples=None,
                                                      skipSubmodules=skipSubmodules, outer=wsDir))

        if len(launchers):
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
        print(e.gitOutput)
    raise mre

def fetchLocal(repo='unknown', branch='master'):
    # branch is actually the list of branches
    branches = branch
    if not branches:
        return

    with utility.cd(repo):
        currentBranch = git.currentBranch()

        git.fetch("--prune")
        git.fetch("--tags --force")
        allRemoteBranches = git.remoteBranches()
        fetchArgs = "origin "
        toFetch = []
        for b in branches:
            if b != currentBranch:
                if f"origin/{b}" in allRemoteBranches:
                    fetchArgs += f"{b}:{b} "
                    toFetch.append(b)
            else:
                try:
                    vine_logging.printMsg(
                        f"Pulling current branch {currentBranch} in {repo}")
                    git.pull(f"origin {currentBranch}")
                except grape_errors.GrapeGitError:
                    print(f"GRAPE: Could not pull {currentBranch} from" + 
                          " origin. Maybe you haven't pushed it yet?")
        try:
            if toFetch:
                vine_logging.printMsg(f"updating {','.join(toFetch)} in {repo}")
                git.fetch(fetchArgs)
        except grape_errors.GrapeGitError as e:
            # let non-fast-forward fetches slide
            if "rejected" in e.gitOutput and "non-fast-forward" in e.gitOutput:
                print(e.gitCommand)
                print(e.gitOutput)
                print("GRAPE: WARNING: one of your public branches " +
                      f"{','.join(branches)} in {repo} has local commits! " +
                      "Did you forget to create a topic branch?")
            elif "Refusing to fetch into current branch" in e.gitOutput:
                print(e.gitOutput)
            else:
                raise e
