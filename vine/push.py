import logging
from vine import config_parser_global
from vine import grape_errors
from vine import grapeGit as git
from vine import multi_repo_cmd_launcher
from vine.option import Option
from vine.workspace_dir_handler import WorkspaceDirHandler
from vine.vine_logging import log_wrapper


class Push(Option, WorkspaceDirHandler):
    """
    grape push pushes your current branch to origin for your outer level repo and all submodules.
    it uses 'git push -u origin HEAD' for the git command.

    Usage: grape-push [--noRecurse]

    Options:
    --noRecurse     Don't perform pushes in submodules.

    """
    def __init__(self):
        super(Push, self).__init__()
        self._key = "push"
        self._section = "Workspace"

    def description(self):
        return "Pushes your current branch to origin in all projects in this workspace."

    @log_wrapper
    def execute(self, args):
        git.currentBranch(execution_path=self.workspace_dir)
        config = config_parser_global.grapeConfig()
        config.getPublicBranchList()

        git.getActiveSubmodules(execution_path=self.workspace_dir)

        launcher = multi_repo_cmd_launcher.MultiRepoCommandLauncher(
            push, execution_path=self.workspace_dir)
        retvals = launcher.launchFromWorkspaceDir(handleMRE=handlePushMRE)

        logging.info("Pushed current branch to origin")
        return False not in retvals

    def setDefaultConfig(self, config):
        pass

def push(repo='', branch='master', *, execution_path):
    logging.info(f"Pushing {branch} in {repo}...")
    git.push(f"-u origin {branch}", throwOnFail=True, execution_path=repo)

def handlePushMRE(mre):
    for e1 in mre.exceptions():
        try:
            raise e1
        except grape_errors.GrapeGitError as e:
            logging.error("Failed to push branch.")
            logging.error(e.gitCommand)
            logging.error(e.cwd)
            logging.error(e.gitOutput)
            return False

if __name__ == "__main__":
    from vine import grapeMenu
    menu = grapeMenu.menu()
    menu.applyMenuChoice("push", [])
