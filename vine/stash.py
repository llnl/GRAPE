import logging
from vine import grape_errors
from vine import grapeGit as git
from vine import multi_repo_cmd_launcher
from vine.workspace_dir_handler import WorkspaceDirHandler
from vine.option import Option
from vine.vine_logging import log_wrapper


def stashHelper(repo=".", branch="", *, workspace_dir):
    return [repo, git.stash(execution_path=repo)]

def popHelper(repo=".", branch="", *, workspace_dir):
    return [repo, git.stash("pop", execution_path=repo)]

def listHelper(repo=".", branch="", *, workspace_dir):
    return [repo, git.stash("list", execution_path=repo)]

class Stash(Option, WorkspaceDirHandler):
    """
    grape stash can run simple git stash, git stash pop, or git stash list commands in all repositories
    in your workspace.

    Note that this is a bit scary - a simple git stash pop will attempt to apply the most recently stashed
    commit in each repo, grape makes no attempt of tracking of which commits were stashed on the most recent
    call to grape stash, so if you do a stash with active edits in one repo, then later do a stash with
    active edits in another repo, then grape stash pop will trigger pops in both repos, in a sense breaking First-In-Last-Out semantics that one might expect.

    Usage: grape-stash
           grape-stash pop
           grape-stash list

    """
    def __init__(self):
        super(Stash, self).__init__()
        self._key = "stash"
        self._section = "Workspace"

    def description(self):
        return "Runs git stash in all repos in your workspace."

    @log_wrapper
    def execute(self, args):

        if args["pop"]:
            launcher = multi_repo_cmd_launcher.MultiRepoCommandLauncher(
                popHelper, workspace_dir=self.workspace_dir)
        elif args["list"]:
            launcher = multi_repo_cmd_launcher.MultiRepoCommandLauncher(
                listHelper, workspace_dir=self.workspace_dir)
        else:
            launcher = multi_repo_cmd_launcher.MultiRepoCommandLauncher(
                stashHelper, workspace_dir=self.workspace_dir)
        try:
            retvals = launcher.launchFromWorkspaceDir()
            for r in retvals:
                if r[1]:
                    logging.info(f"{r[0]}: {r[1]}")
        except grape_errors.MultiRepoException as mre:
            for e, r in zip(mre, mre.repos):
                logging.error(f"{r}:\n{e.gitOutput}")

        return True

    def setDefaultConfig(self, config):
        pass
