import logging
from vine import grape_errors
from vine import grapeGit as git
from vine import merge
from vine import multi_repo_cmd_launcher
from vine import utility
from vine.workspace_dir_handler import WorkspaceDirHandler
from vine.option import Option
from vine.vine_logging import log_wrapper


#merge a remote branch into this branch
class MergeRemote(Option, WorkspaceDirHandler):
    """
    grape mr (merge remote branch). If the remote branch is different from your current branch, this will update
    or add a local version of that branch, then merge it into your current branch. If you perform a grape mr on the
    current branch or if the remote branch can not be fastforward merged into your local version of that branch,
    then this will do a merge assuming the remote branch has a different line of development than
    your local branch. (Ideal for developers working on shared branches.)

    Usage: grape-mr [<branch>] [--am | --as | --at | --aT | --ay | --aY ] [--continue] [--noRecurse] [--noUpdate] [--squash]


    Options:
        --am                    Perform the merge using git's default strategy.
        --as                    Perform the merge issuing conflicts on any file modified by both branches.
        --at                    Perform the merge using the remote branch's version for any file modified by both branches.
        --aT                    Perform the merge resolving conficts using the remote branch's version.
        --ay                    Perform the merge resolving conflicts using your topic branch's version.
        --aY                    Perform the merge using your topic branch's version for any file modified by both branches.
        --noRecurse             Perform the merge in the current repository only. Otherwise, this will call
                                grape md --public=<branch> to handle submodule and nested project merges.
        --continue              Resume your previous merge after resolving conflicts.
        --squash                Perform squash merges.

    Arguments:
    <branch>      The name of the remote branch to merge in (without remote/origin or origin/ prefix)

    """
    def __init__(self):
        super(MergeRemote, self).__init__()
        self._key = "mr"
        self._section = "Merge"

    def description(self):
        return "Merge a remote branch into your current branch."

    @log_wrapper
    def execute(self, args):
        # Imported here to avoid circular dependencies
        from vine import grapeMenu

        if "<<cmd>>" not in args:
            args["<<cmd>>"] = "mr"
        otherBranch = args['<branch>']
        if not otherBranch:
            # list remote branches that are available
            logging.info(git.branch('-r', execution_path=self.workspace_dir))
            otherBranch = utility.userInput("Enter name of branch you would like to merge into this branch (without the origin/ prefix)")

        # make sure remote references are up to date
        logging.info("Fetching remote references in all projects...")
        try:
            launcher = multi_repo_cmd_launcher.MultiRepoCommandLauncher(
                fetchHelper, execution_path=self.workspace_dir)
            launcher.launchFromWorkspaceDir()
        except grape_errors.MultiRepoException as mre:
            commError = False
            commErrorRepos = []
            for e, r in zip(mre.exceptions(), mre.repos()):
                if e.commError:
                    commErrorRepos.append(r)
                    commError = True

            if commError:
                logging.error("ERROR: can't communicate with remotes for " +
                              f"{commErrorRepos}. Halting remote merge.")
                return False

        # update our local reference to the remote branch so long as it's fast-forwardable or we don't have it yet..)
        hasRemote = git.join_list_as_git_path(['origin', otherBranch]) in git.remoteBranches(execution_path=self.workspace_dir)
        hasBranch = git.hasBranch(otherBranch, execution_path=self.workspace_dir)
        currentBranch = git.currentBranch(execution_path=self.workspace_dir)
        remote_other_branch = git.join_list_as_git_path(['remotes', 'origin', otherBranch])
        remoteUpToDateWithLocal = git.branchUpToDateWith(remote_other_branch, otherBranch, execution_path=self.workspace_dir)
        updateLocal = hasRemote and (remoteUpToDateWithLocal or not hasBranch) and currentBranch != otherBranch
        if updateLocal:
            origin_other_branch = git.join_list_as_git_path(['origin', otherBranch])
            logging.info(f"updating local branch {otherBranch} " +
                         f"from {origin_other_branch}")
            launcher = multi_repo_cmd_launcher.MultiRepoCommandLauncher(
                updateBranchHelper, branch=otherBranch,
                execution_path=self.workspace_dir)
            launcher.launchFromWorkspaceDir(handleMRE=updateBranchHandleMRE)

        args["<branch>"] = otherBranch if updateLocal else git.join_list_as_git_path(['origin', otherBranch])
        # we've handled the update, we don't want m or md to update the local branch.
        args["--noUpdate"] = True
        # if mr is called by the user, need to initialize the --continue argument.
        # if it is called by md, it will be set already.
        if "--continue" not in args:
            args["--continue"] = False

        merge_command = grapeMenu.menu().getOption('m')
        merge_command.workspace_dir = self.workspace_dir
        return merge_command.execute(args)

    def setDefaultConfig(self, config):
        pass

def fetchHelper(repo="unknown", branch="master", *, workspace_dir):
    return git.fetch("origin", warnOnCommError=False, raiseOnCommError=True, execution_path=repo)

def updateBranchHelper(repo="unknown", branch="master", *, workspace_dir):
    logging.info(f"Updating local reference to {branch} in {repo}")
    return git.fetch(f"origin {branch}:{branch}", execution_path=repo)

def updateBranchHandleMRE(mre):
    for e, repo, branch in zip(mre.exceptions(), mre.repos(), mre.branches()):
        if e.could_not_find_remote_ref():
            logging.info(
                f"Remote reference to {branch} not present in {repo}. " +
                "Remote ref must be present in all active submodules to " +
                "merge.\n\tEither create placeholder branches or deactivate" +
                " submodules to resolve. ")
    raise mre
