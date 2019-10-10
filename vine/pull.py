import logging
from vine import grapeGit as git
from vine.option import Option
from vine.command_path_handler import CommandPathHandler
from vine.resumable import Resumable
from vine.vine_logging import log_wrapper


class Pull(Resumable, Option, CommandPathHandler):
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
        self.set_progress_file(execution_path=self.command_path)

        mrArgs = {}
        currentBranch = git.currentBranch(execution_path=self.command_path)
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
        mrArgs["--ask"] = False
        mrArgs["--askAll"] = False
        mrArgs["--continue"] = args["--continue"]
        mrArgs["--noRecurse"] = False
        mrArgs["--squash"] = False

        if args["--noRecurse"]:
            git.pull(f"origin {currentBranch}", execution_path=self.command_path)
            logging.info("Pulled current branch from origin")
            return True
        # Imported here to avoid circular dependencies
        from vine import grapeMenu

        merge_remote_command = grapeMenu.menu().getOption("mr")
        merge_remote_command.command_path = self.command_path
        val = merge_remote_command.execute(mrArgs)
        if val:
            logging.info("Pulled current branch from origin")
        return val

    def _resume(self, args, *, workspace_dir):
        # Imported here to avoid circular dependencies
        from vine import grapeMenu
        merge_down_command = grapeMenu.menu().getOption("md")
        merge_down_command.command_path = self.command_path
        merge_down_command._resume(args, workspace_dir)
        return True

    def _saveProgress(self, args):
        super(Pull, self)._saveProgress(args)

    def setDefaultConfig(self, config):
        pass
