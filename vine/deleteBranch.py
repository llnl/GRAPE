import logging
from vine import grape_errors
from vine import grapeGit as git
from vine import multi_repo_cmd_launcher
from vine import option
from vine import utility
from vine import vine_logging
from vine.vine_logging import log_wrapper


class DeleteBranch(option.Option):
    """ Deletes a topic branch both locally and on origin for all projects in this workspace.
    Usage: grape-db [-D] [<branch>] [--verify]

    Options:
    -D              Forces the deletion of unmerged branches. If you are on the branch you
                    are trying to delete, this will detach you from the branch and then
                    delete it, issuing a warning that you are in a detached state.
     --verify       Verifies the delete before performing it.

    Arguments:
    <branch>        The branch to delete. Will ask for branch name if not included.


    """
    def __init__(self):
        super(DeleteBranch, self).__init__()
        self._key = "db"
        self._section = "Gitflow Tasks"

    def description(self):
        return "Delete a branch on both your local repo and on origin"



    @log_wrapper
    def execute(self, args):
        branch = args["<branch>"]
        force = args["-D"]
        if not branch:
            branch = utility.userInput("Enter name of branch to delete")


        if args["--verify"]:
            proceed = utility.userInput("Would you like to delete the " +
                                        f"branch {branch}", 'y')
            if not proceed:
                return True

        launcher = multi_repo_cmd_launcher.MultiRepoCommandLauncher(deleteBranch,
                                            branch=branch,
                                            globalArgs=[force])
        try:
            launcher.launchFromWorkspaceDir()
        except grape_errors.MultiRepoException as e:
            handleDeleteBranchMRE(e, force)

        return True

    def setDefaultConfig(self, config):
        pass



def deleteBranch(repo='', branch='master', args = None):
    force = args[0]
    forceStr = "-D" if force is True else "-d"
    with git.cd(repo):
        logging.info(f"deleting {branch} in {repo}...")
        git.branch(f"{forceStr} {branch}")
        if f"origin/{branch}" in git.branch("-r"):
            try:
                git.push(f"--delete origin {branch}", throwOnFail=True)
            except grape_errors.GrapeGitError as e:
                if "remote ref does not exist" in e.gitOutput:
                    pass

def detachThenForceDeleteBranch(repo='', branch='master', args = None):
    with git.cd(repo):
        logging.warning(
            f"*** WARNING ***: Detaching in order to delete {branch} in " +
            f"{repo}. You will be in a headless state.")
        git.checkout("--detach HEAD")
        git.branch(f"-D {branch}")
        if f"origin/{branch}" in git.remoteBranches():
            git.push(f"--delete origin {branch}", throwOnFail=False)

def handleDetachThenForceMRE(mre):
    # this shouldn't happen, but here is some verbosity for when it does...
    for e1, branch, repo in zip(mre.exceptions(), mre.branches(), mre.repos()):
        logging.error(f"{e1} {branch} {repo}")
    raise mre

def handleDeleteBranchMRE(mre, force=False):
    detachTuples = []
    for e1, branch, repo in zip(mre.exceptions(), mre.branches(), mre.repos()):
        try:
            raise e1
        except grape_errors.GrapeGitError as e:
            with git.cd(repo):
                if "Cannot delete the branch" in e.gitOutput and \
                   "which you are currently on." in e.gitOutput:
                    if force:
                        detachTuples.append((repo, branch, None))
                    else:
                        logging.info(
                            f"call grape db -D {branch} to force deletion" +
                            " of branch you are currently on.")
                elif "not deleting branch" in e.gitOutput and "even though it is merged to HEAD." in e.gitOutput:
                    git.branch(f"-D {branch}")
                elif "error: branch" in e.gitOutput and "not found" in e.gitOutput:
                    logging.info(f"{branch} not found in {repo}")
                elif "is not fully merged" in e.gitOutput:
                    if force:
                        logging.info(f"**DELETING UNMERGED BRANCH {branch}")
                        git.branch(f"-D {branch}")
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

    multi_repo_cmd_launcher.MultiRepoCommandLauncher(detachThenForceDeleteBranch,
                             listOfRepoBranchArgTuples=detachTuples).launchFromWorkspaceDir(handleMRE=handleDetachThenForceMRE)
