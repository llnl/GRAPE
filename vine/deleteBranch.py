import logging
from vine import grape_errors
from vine import grapeGit as git
from vine import multi_repo_cmd_launcher
from vine.option import Option
from vine.workspace_dir_handler import WorkspaceDirHandler
from vine import utility
from vine.vine_logging import log_wrapper


class DeleteBranch(Option, WorkspaceDirHandler):
    """ Deletes a topic branch both locally and on origin for all projects in this workspace.
    Usage: grape-db [-D] [<branch>...] [--verify] [--local-only|--remote-only] [--inactive-repos]

    Options:
    -D                Forces the deletion of unmerged branches. If you are on the branch you
                      are trying to delete, this will detach you from the branch and then
                      delete it, issuing a warning that you are in a detached state.
    --local-only      Only deletes the local branch.
    --remote-only     Only deletes the remote branch.
    --verify          Verifies the delete before performing it.
    --inactive-repos  Deletes the remote branch in any repos that are not currently active in your workspace.

    Arguments:
    <branch>         The branches to delete. Will ask for branch name if not included.


    """
    def __init__(self):
        super(DeleteBranch, self).__init__()
        self._key = "db"
        self._section = "Gitflow Tasks"

    def description(self):
        return "Delete a branch on both your local repo and on origin"

    @log_wrapper
    def execute(self, args):
        branches = args["<branch>"]
        force = args["-D"]
        delete_remote = not args["--local-only"] or args["--inactive-repos"]
        delete_local = not args["--remote-only"] and not args["--inactive-repos"]


        if not branches:
            branches = [utility.userInput("Enter name of branch to delete")]

        if args["--verify"]:
            proceed = utility.userInput("Would you like to delete the " +
                                        f"branch {branch}", 'y')
            if not proceed:
                return True

        for branch in branches:

            current_branch = git.currentBranch(execution_path=self.workspace_dir)

            if current_branch == branch and not force and delete_local:
                logging.info("Cannot delete the branch you are currently on.  " +
                             "Use -D to detach and then delete branch.")
                return False
            elif current_branch == branch and force and delete_local:
                launcher = multi_repo_cmd_launcher.MultiRepoCommandLauncher(
                    detachThenForceDeleteBranch, branch=branch, globalArgs=[delete_local, delete_remote],
                    workspace_dir=self.workspace_dir)
            else:
                inactive = args["--inactive-repos"]
                launcher = multi_repo_cmd_launcher.MultiRepoCommandLauncher(
                    deleteBranch, runInSubmodules= not inactive, runInOuter= not inactive, runInSubprojects=not inactive, branch=branch, globalArgs=[force, delete_local, delete_remote],
                    workspace_dir=self.workspace_dir, inactive_repos= inactive)
            try:
                launcher.launchFromWorkspaceDir()
            except grape_errors.MultiRepoException as e:
                handleDeleteBranchMRE(e, force, delete_local, delete_remote)

        return True

    def setDefaultConfig(self, config):
        pass


def deleteBranch(repo='', branch='master', args=None, *, workspace_dir, remote_url):
    force = args[0]
    delete_local = args[1]
    delete_remote = args[2]
    if remote_url:
        remote = remote_url
    else:
        remote = "origin"

    if delete_local:
        forceStr = "-D" if force is True else "-d"
        logging.info(f"deleting {branch} in {repo}...")
        try:
            git.branch(f"{forceStr} {branch}", execution_path=repo)
        except grape_errors.GrapeGitError as e:
            if "branch" in e.gitOutput and "not found." in e.gitOutput:
                logging.warning(f"local branch origin/{branch} not found in {repo}")
            else:
                raise e

    if delete_remote:
        logging.info(f"deleting {remote}/{branch} in {repo}...")
        try:
            git.push(f"--delete {remote} {branch}", throwOnFail=True, execution_path=repo)
        except grape_errors.GrapeGitError as e:
            if "remote ref does not exist" in e.gitOutput.lower():
                logging.warning(f"remote branch origin/{branch} not found in {repo}")
                pass
        try:
            git.branch(f"-dr origin/{branch}", execution_path=repo)
        except grape_errors.GrapeGitError as e:
            if "remote tracking branch" in e.gitOutput and "not found" in e.gitOutput:
                logging.warning(f"remote tracking branch origin/{branch} not found in {repo}")
                pass



def detachThenForceDeleteBranch(repo='', branch='master', args=None, *, workspace_dir):
    delete_local = args[0]
    delete_remote = args[1]

    if delete_local:
        logging.warning(
            f"*** WARNING ***: Detaching in order to delete {branch} in " +
            f"{repo}. You will be in a headless state.")
        git.checkout("--detach HEAD", execution_path=repo)
        git.branch(f"-D {branch}", execution_path=repo)

    if delete_remote:
        logging.info(f"deleting origin/{branch} in {repo}...")
        if f"origin/{branch}" in git.remoteBranches(execution_path=repo):
            git.push(f"--delete origin {branch}", throwOnFail=False, execution_path=repo)
        else:
            logging.warning(f"remote branch origin/{branch} not found in {repo}")
        try:
            git.branch(f"-dr origin/{branch}", execution_path=repo)
        except grape_errors.GrapeGitError as e:
            if "remote tracking branch" in e.gitOutput and "not found" in e.gitOutput:
                logging.warning(f"remote tracking branch origin/{branch} not found in {repo}")
                pass



def handleDetachThenForceMRE(mre):
    # this shouldn't happen, but here is some verbosity for when it does...
    for e1, branch, repo in zip(mre.exceptions(), mre.branches(), mre.repos()):
        logging.error(f"{e1} {branch} {repo}")
    raise mre

def handleDeleteBranchMRE(mre, force=False, delete_local=True, delete_remote=True):
    detachTuples = []
    for e1, branch, repo in zip(mre.exceptions(), mre.branches(), mre.repos()):
        try:
            raise e1
        except grape_errors.GrapeGitError as e:
            if "cannot delete the branch" in e.gitOutput.lower() and \
               "which you are currently on." in e.gitOutput.lower():
                if force:
                    detachTuples.append((repo, branch, None))
                else:
                    logging.info(
                        f"call grape db -D {branch} to force deletion" +
                        " of branch you are currently on.")
            elif "not deleting branch" in e.gitOutput.lower() and "even though it is merged to head." in e.gitOutput.lower():
                git.branch(f"-D {branch}", execution_path=repo)
            elif "error: branch" in e.gitOutput.lower() and "not found" in e.gitOutput.lower():
                logging.info(f"{branch} not found in {repo}")
            elif "is not fully merged" in e.gitOutput.lower():
                if force:
                    logging.info(f"**DELETING UNMERGED BRANCH {branch}")
                    git.branch(f"-D {branch}", execution_path=repo)
                else:
                    logging.info(
                        f"{branch} is not fully merged in {repo}. " +
                        f"Run grape db -D {branch} to force the deletion")
            elif e.commError:
                logging.warning(
                    "Could not connect to origin to delete remote " +
                    "references to your branch. You may want to call " +
                    f"grape db {branch} again once you've reconnected.")
            else:
                logging.error(f"Deletion of {branch} failed for " +
                              "unhandled reason.")
                logging.error(e.gitOutput)
                raise e

    launcher = multi_repo_cmd_launcher.MultiRepoCommandLauncher(
        detachThenForceDeleteBranch, listOfRepoBranchArgTuples=detachTuples, globalArgs=[delete_local, delete_remote],
        workspace_dir=mre.workspace_dir)
    launcher.launchFromWorkspaceDir(handleMRE=handleDetachThenForceMRE)
