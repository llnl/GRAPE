import logging
import os
from vine import config
from vine import config_parser_global
from vine import config_parser_user
from vine import grape_errors
from vine import grapeGit as git
from vine import multi_repo_cmd_launcher
from vine.workspace_dir_handler import WorkspaceDirHandler
from vine.option import Option
from vine.vine_logging import log_wrapper


class Status(Option, WorkspaceDirHandler):
    """
    Usage: grape-status [-u | --uno]
              [--failIfInconsistent]
              [--failIfMissingPublicBranches]
              [--failIfBranchesInconsistent]
              [--checkWSOnly]

    Options:
    --uno                          Do not show untracked files
    -u                             Show untracked files.
    --failIfInconsistent           Fail if any consistency checks fail.
    --failIfMissingPublicBranches  Fail if your workspace or your origin's workspace is missing public branches.
    --failIfOnInconsistentBranches Fail if your subprojects are on branches that are inconsistent with what is checked out in your workspace.
    --checkWSOnly                  Only check the workspace's projects' branches for consistency. Don't gather git statuses.


    """
    def __init__(self):
        super(Status, self).__init__()
        self._key = "status"
        self._section = "Workspace"

    def description(self):
        return "Gives the status for this workspace"

    # print the status for the entire workspace
    def printStatus(self, args):
        statusArgs = ""
        if args["-u"]:
            statusArgs += "-u "
        if args["--uno"]:
            statusArgs += "-uno "

        launcher = multi_repo_cmd_launcher.MultiRepoCommandLauncher(getStatus,
                                            runInSubmodules=True,
                                            runInSubprojects=True,
                                            runInOuter=True,
                                            globalArgs=[statusArgs, self.workspace_dir],
                                            execution_path=self.workspace_dir)
        stati = launcher.launchFromWorkspaceDir(noPause=True)
        status = {}
        for s, r in (zip(stati, launcher.repos)):
            status[r] = s

        for sub in status.keys():
            for line in status[sub]:
                lstripped = line.strip()
                if lstripped:
                    # print other statuses
                    logging.info(f' {lstripped}')

    def checkForLocalPublicBranches(self, args):
        publicBranchesExist = True
        # Check that all public branches exist locally.
        cfg = config_parser_global.grapeConfig()
        publicBranches = cfg.getPublicBranchList()
        missingBranches = config.Config.checkIfPublicBranchesExist(self.workspace_dir,
                                                                   publicBranches)

        if len(missingBranches) > 0:
            for mb in missingBranches:
                logging.info(f"Repository is missing public branch {mb}, attempting to fetch it now...")
                try:
                    git.fetch(f"origin {mb}:{mb}",
                              execution_path=self.workspace_dir)
                    logging.info(f"{mb} added as a local branch")
                except grape_errors.GrapeGitError as e:
                    logging.error(e.gitOutput)
                    publicBranchesExist = False
        return publicBranchesExist

    def checkForConsistentWorkspaceBranches(self, args):
        consistentBranchState = True
        cfg = config_parser_global.grapeConfig()
        publicBranches = cfg.getPublicBranchList()
        wsBranch = git.currentBranch(execution_path=self.workspace_dir)
        subPubMap = cfg.getMapping(self.SECTION_WORKSPACE, "submodulepublicmappings")
        if wsBranch in publicBranches:
            for sub in git.getActiveSubmodules(execution_path=self.workspace_dir):
                subbranch = git.currentBranch(execution_path=os.path.join(self.workspace_dir, sub))
                if subbranch != subPubMap[wsBranch]:
                    consistentBranchState = False
                    logging.info(f"Submodule {sub} on branch {subbranch} when grape expects it to be on {subPubMap[wsBranch]}")
        else:
            for sub in git.getActiveSubmodules(execution_path=self.workspace_dir):
                subbranch = git.currentBranch(execution_path=os.path.join(self.workspace_dir, sub))
                if subbranch != wsBranch:
                    consistentBranchState = False
                    logging.info(f"Submodule {sub} on branch {subbranch}" +
                                 f" when grape expects it to be on {wsBranch}")

        # check that nested subproject branching is consistent
        for nested in config_parser_user.getAllActiveNestedSubprojectPrefixes(workspaceDir=self.workspace_dir):
            nestedbranch = git.currentBranch(execution_path=os.path.join(self.workspace_dir, nested))
            if nestedbranch != wsBranch:
                consistentBranchState = False
                logging.info(f"Nested Project {nested} on branch " +
                             f"{nestedbranch} when grape expects " +
                             f"it to be on {wsBranch}")

        return consistentBranchState

    @log_wrapper
    def execute(self, args):
        if not args["--checkWSOnly"]:
            self.printStatus(args)
        # Sanity check workspace layout
        publicBranchesExist = self.checkForLocalPublicBranches(args)
        # Check that submodule branching is consistent
        consistentBranchState = self.checkForConsistentWorkspaceBranches(args)

        retval = True
        if args["--failIfInconsistent"]:
            retval = retval and publicBranchesExist and consistentBranchState
        if args["--failIfMissingPublicBranches"]:
            retval = retval and publicBranchesExist
        if args["--failIfBranchesInconsistent"]:
            retval = retval and consistentBranchState
        return retval


    def setDefaultConfig(self, config):
        pass

def getStatus(branch='', repo='', args='', *, execution_path):
    statusArgs = args[0]
    wsDir = args[1]
    toReturn = []

    if not repo.strip():
        return ""
    try:
        if wsDir == repo:
            relPath = ""
            pathSpec = "[workspace]"
        else:
            relPath = os.path.relpath(repo, wsDir)
            pathSpec = relPath

        # Identify if the repo is still merging (this does not show up in short formats)
        subStatusLong = git.status(f"--long -uno", execution_path=repo).split('\n')
        if "All conflicts fixed but you are still merging." in subStatusLong:
            toReturn.append(f" {pathSpec}: You are still merging")

        # Get the status of each file as well as the branch status
        subStatus = git.status(f"--porcelain -b {statusArgs}", execution_path=repo).split('\n')

        for line in subStatus:
            strippedL = line.strip()
            if strippedL:
                # filter out branch tracking status unless ahead or behind
                # ## bugfix/bugfixday/DLThreadSafety...remotes/origin/bugfix/bugfixday/DLThreadSafety [ahead 1]
                # ## bugfix/bugfixday/DLThreadSafety...remotes/origin/bugfix/bugfixday/DLThreadSafety [behind 29]
                if strippedL[0:2] == "##":
                   if "[ahead" in strippedL or "[behind" in strippedL:
                       toReturn.append(f"{pathSpec}: {strippedL}")
                else:
                   tokens = strippedL.split()
                   tokens[0] = tokens[0].strip()
                   if len(tokens) == 2:
                       if len(tokens[0]) == 1:
                          tokens[0] = f" {tokens[0]} "
                       branch_path = os.path.join(relPath, tokens[1])
                       toReturn.append(' '.join([tokens[0], branch_path]))
                   else:
                       toReturn.append(' '.join(tokens))

        return toReturn
    except Exception as e:
        logging.error(e)
