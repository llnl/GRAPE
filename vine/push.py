import os
from grape.vine import config_parser_global
from grape.vine import grape_errors
from grape.vine import grapeGit as git
from grape.vine import multi_repo_cmd_launcher
from grape.vine import utility
from grape.vine import vine_logging
from grape.vine.option import Option


class Push(Option):
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

    def execute(self, args):
        baseDir = utility.workspaceDir()

        with utility.cd_workspace():
            currentBranch = git.currentBranch()
            config = config_parser_global.grapeConfig()
            publicBranches = config.getPublicBranchList()

            submodules = git.getActiveSubmodules(baseDir)

            retvals = multi_repo_cmd_launcher.MultiRepoCommandLauncher(push).launchFromWorkspaceDir(handleMRE=handlePushMRE)

        vine_logging.printMsg("Pushed current branch to origin")
        return False not in retvals

    def setDefaultConfig(self, config):
        pass

def push(repo='', branch='master'):
    with git.cd(repo):
        vine_logging.printMsg(f"Pushing {branch} in {repo}...")
        git.push(f"-u origin {branch}", throwOnFail=True)

def handlePushMRE(mre):
    for e1 in mre.exceptions():
        try:
            raise e1
        except grape_errors.GrapeGitError as e:
            vine_logging.printMsg("Failed to push branch.")
            print(e.gitCommand)
            print(e.cwd)
            print(e.gitOutput)
            return False

if __name__ is "__main__":
    from grape.vine import grapeMenu
    menu = grapeMenu.menu()
    menu.applyMenuChoice("push", [])
