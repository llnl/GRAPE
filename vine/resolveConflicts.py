import os
from vine import grapeGit as git
from vine.command_path_handler import CommandPathHandler
from vine.option import Option
from vine.vine_logging import log_wrapper


# resolve conflicts using git mergetool
class ResolveConflicts(Option, CommandPathHandler):

    def __init__(self):
        super(ResolveConflicts, self).__init__()
        self._key = "resolve"
        self._section = "Merge"

    def description(self):
        return "Resolve Conflicts that arose as result of a merge or a rebase"

    @log_wrapper
    def execute(self, args):
        self.set_progress_file(self.command_path)

        git.gitcmd("mergetool", "Mergetool Failed",
                   execution_path=self.command_path)
        # print out git status, which contains instructions to complete a merge
        git.status(execution_path=self.command_path)
        return True

    def setDefaultConfig(self, config):
        pass
