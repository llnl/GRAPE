import logging
import os
from vine import config_parser_global
from vine import grape_errors
from vine import grapeGit as git
from vine import multi_repo_cmd_launcher
from vine import utility
from vine import vine_logging
from vine.option import Option
from vine.command_path_handler import CommandPathHandler
from vine.vine_logging import log_wrapper


class Push(Option, CommandPathHandler):
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
        currentBranch = git.currentBranch(execution_path=self.workspace_dir)
        config = config_parser_global.grapeConfig()
        publicBranches = config.getPublicBranchList()

        submodules = git.getActiveSubmodules(self.workspace_dir)

        launcher = multi_repo_cmd_launcher.MultiRepoCommandLauncher(
            push, execution_path=self.command_path)
        retvals = launcher.launchFromWorkspaceDir(handleMRE=handlePushMRE)

        logging.info("Pushed current branch to origin")
        return False not in retvals

    def setDefaultConfig(self, config):
        pass

def push(repo='', branch='master', *, execution_path):
    logging.info(f"Pushing {branch} in {execution_path}...")
    git.push(f"-u origin {branch}", throwOnFail=True, execution_path=execution_path)

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

if __name__ is "__main__":
    from vine import grapeMenu
    menu = grapeMenu.menu()
    menu.applyMenuChoice("push", [])
