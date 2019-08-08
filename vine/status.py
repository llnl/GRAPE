import logging
import os
from vine import config
from vine import config_parser_global
from vine import config_parser_user
from vine import grape_errors
from vine import grapeGit as git
from vine import multi_repo_cmd_launcher
from vine import utility
from vine import vine_logging
from vine.option import Option
from vine.vine_logging import log_wrapper


class Status(Option):
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
        wsDir = utility.workspaceDir()
        statusArgs = ""
        if args["-u"]:
            statusArgs += "-u "
        if args["--uno"]:
            statusArgs += "-uno "

        launcher = multi_repo_cmd_launcher.MultiRepoCommandLauncher(getStatus,
                                            runInSubmodules=True,
                                            runInSubprojects=True,
                                            runInOuter=True,
                                            globalArgs=[statusArgs, wsDir])

        stati = launcher.launchFromWorkspaceDir(noPause=True)
        status = {}
        for s, r in (zip(stati, launcher.repos)):
            status[r] = s

        for sub in status.keys():
            for line in status[sub]:
                lstripped = line.strip()
                if lstripped:
                    # filter out branch tracking status
                    # ## bugfix/bugfixday/DLThreadSafety...remotes/origin/bugfix/bugfixday/DLThreadSafety [ahead 1]
                    # ## bugfix/bugfixday/DLThreadSafety...remotes/origin/bugfix/bugfixday/DLThreadSafety [behind 29]
                    if lstripped[0:2] == "##":
                        if "[ahead" in lstripped or "[behind" in lstripped:
                            logging.info(
                                f"{os.path.abspath(os.path.join(wsDir, sub))}"+
                                f": {lstripped}")
                        continue
                    # print other statuses
                    logging.info(f' {lstripped}')

    def checkForLocalPublicBranches(self, args):
        publicBranchesExist = True
        # Check that all public branches exist locally.
        cfg = config_parser_global.grapeConfig()
        publicBranches = cfg.getPublicBranchList()
        missingBranches = config.Config.checkIfPublicBranchesExist(utility.workspaceDir(),
                                                                   publicBranches)

        if len(missingBranches) > 0:
            for mb in missingBranches:
                logging.info(f"Repository is missing public branch {mb}, attempting to fetch it now...")
                try:
                    git.fetch(f"origin {mb}:{mb}")
                    logging.info(f"{mb} added as a local branch")
                except grape_errors.GrapeGitError as e:
                    logging.error(e.gitOutput)
                    publicBranchesExist = False
        return publicBranchesExist

    def checkForConsistentWorkspaceBranches(self, args):
        consistentBranchState = True
        cfg = config_parser_global.grapeConfig()
        publicBranches = cfg.getPublicBranchList()
        wsDir = utility.workspaceDir()
        os.chdir(wsDir)
        wsBranch = git.currentBranch()
        subPubMap = cfg.getMapping(self.SECTION_WORKSPACE, "submodulepublicmappings")
        if wsBranch in publicBranches:
            for sub in git.getActiveSubmodules(wsDir):
                os.chdir(os.path.join(wsDir,sub))
                subbranch = git.currentBranch()
                if subbranch != subPubMap[wsBranch]:
                    consistentBranchState = False
                    logging.info(f"Submodule {sub} on branch {subbranch} when grape expects it to be on {subPubMap[wsBranch]}")
        else:
            for sub in git.getActiveSubmodules(wsDir):
                os.chdir(os.path.join(wsDir,sub))
                subbranch = git.currentBranch()
                if subbranch != wsBranch:
                    consistentBranchState = False
                    logging.info(f"Submodule {sub} on branch {subbranch}" +
                                 " when grape expects it to be on {wsBranch}")

        # check that nested subproject branching is consistent
        for nested in config_parser_user.getAllActiveNestedSubprojectPrefixes():
            os.chdir(os.path.join(wsDir, nested))
            nestedbranch = git.currentBranch()
            if nestedbranch != wsBranch:
                consistentBranchState = False
                logging.info(f"Nested Project {nested} on branch " +
                             f"{nestedbranch} when grape expects " +
                             f"it to be on {wsBranch}")

        return consistentBranchState

    @log_wrapper
    def execute(self, args):
        with utility.cd_workspace():
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

def getStatus(branch='', repo='', args=''):
    statusArgs = args[0]
    wsDir = args[1]
    toReturn = []

    sub = repo
    if not sub.strip():
        return ""
    try:

        with git.cd(sub):
            subStatus = git.status(f"--porcelain -b {statusArgs}").split('\n')
            for line in subStatus:
                strippedL = line.strip()
                if strippedL:
                    tokens = strippedL.split()
                    tokens[0] = tokens[0].strip()
                    if len(tokens[0]) == 1:
                        tokens[0] = f" {tokens[0]} "
                    if wsDir == sub:
                        relPath = ""
                        toReturn.append(' '.join([tokens[0], tokens[1]]))
                    else:
                        relPath = os.path.relpath(sub, wsDir)
                        branch_path = git.join_list_as_git_path([relPath, tokens[1]])
                        toReturn.append(' '.join([tokens[0], branch_path]))
        return toReturn
    except Exception as e:
        logging.error(e)
