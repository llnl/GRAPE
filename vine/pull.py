import logging
from vine import grapeGit as git
from vine.option import Option
from vine.workspace_dir_handler import WorkspaceDirHandler
from vine.resumable import Resumable
from vine.vine_logging import log_wrapper


class Pull(Resumable, Option, WorkspaceDirHandler):
    """
    grape pull pulls any updates to your current branch into for your outer level repo and all subprojects.
    Since a pull is really a remote merge, this is the same as grape mr <currentBranch>.

    Usage: grape-pull [--continue] [--noRecurse]

    Options:
        --continue     Finish a pull that failed due to merge conflicts.
        --noRecurse    Simply do a git pull origin <currentBranch> in the current directory.


    """
    def __init__(self):
        super(Pull, self).__init__()
        self._key = "pull"
        self._section = "Workspace"

    def description(self):
        return "Pulls your current branch to origin in all projects in this workspace. (Calls grape mr <currentBranch>)"

    @log_wrapper
    def execute(self, args):
        self.set_progress_file(execution_path=self.workspace_dir)

        mrArgs = {}
        currentBranch = git.currentBranch(execution_path=self.workspace_dir)
        remoteBranch = git.join_list_as_git_path(['origin', currentBranch])
        hasRemote = remoteBranch in git.remoteBranches(
            execution_path=self.workspace_dir)
        mrArgs["<branch>"] = currentBranch
        # the <<cmd>> stuff is for consistent --continue output
        if "<<cmd>>" not in args:
            args["<<cmd>>"] = "pull"
        mrArgs["<<cmd>>"] = args["<<cmd>>"]
        mrArgs["--am"] = True
        mrArgs["--as"] = False
        mrArgs["--at"] = False
        mrArgs["--aT"] = False
        mrArgs["--ay"] = False
        mrArgs["--aY"] = False
        mrArgs["--continue"] = args["--continue"]
        mrArgs["--noRecurse"] = False
        mrArgs["--squash"] = False

        if not hasRemote:
            git.fetch("origin", execution_path=self.workspace_dir)
            hasRemote = remoteBranch in git.remoteBranches(
                execution_path=self.workspace_dir)
        if not hasRemote:
            logging.info(
                f"No remote reference to {currentBranch} in origin. "
                "You may want to push this branch.")
            return True

        if args["--noRecurse"]:
            git.pull(f"origin {currentBranch}", execution_path=self.workspace_dir)
            logging.info("Pulled current branch from origin")
            return True
        # Imported here to avoid circular dependencies
        from vine import grapeMenu

        merge_remote_command = grapeMenu.menu().getOption("mr")
        merge_remote_command.workspace_dir = self.workspace_dir
        val = merge_remote_command.execute(mrArgs)
        if val:
            logging.info("Pulled current branch from origin")
        return val

    def _resume(self, args, *, workspace_dir):
        # Imported here to avoid circular dependencies
        from vine import grapeMenu
        merge_down_command = grapeMenu.menu().getOption("md")
        merge_down_command.workspace_dir = self.workspace_dir
        merge_down_command._resume(args, workspace_dir=workspace_dir)
        return True

    def _saveProgress(self, args):
        super(Pull, self)._saveProgress(args)

    def setDefaultConfig(self, config):
        pass
