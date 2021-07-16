from vine import config_parser_global
from vine import utility
from vine.workspace_dir_handler import WorkspaceDirHandler
from vine.option import Option
from vine.resumable import Resumable
from vine.vine_logging import log_wrapper


# merge in a local branch into this branch
#
# NOTE: any updates to merge's arguments should be reflected in Merge Remote's arguments, or at least given values
# by mergeRemote before the call to merge.
class Merge(Resumable, Option, WorkspaceDirHandler):
    """
    grape m
    merge a local branch into your current branch
    Usage: grape-m [<branch>] [--am | --as | --at | --aT | --ay | --aY | --ask | --askAll] [--continue] [--noRecurse] [--noUpdate] [--squash]

    Options:
        --am            Use git's default merge.
        --as            Do a safe merge - force git to issue conflicts for files that
                        are touched by both branches.
        --at            Git accept their changes in any file touched by both branches (the branch you're merging from)
        --aT            Git accept their changes in the event of a conflict (the branch you're merging from)
        --ay            Git will accept your changes in any file touched by both branches (the branch you're currently on)
        --aY            Git will accept your changes in the event of a conflict (the branch you're currently on)
        --noRecurse     Perform the merge in the current repository only. Otherwise, grape md --public=<branch>
                        will be called to handle submodule and nested project merges.
        --continue      Resume your previous merge after resolving conflicts.
        --noUpdate      Don't perform an update of your local version of <branch> from the remote before attempting
                        the merge.
        --squash        Perform squash merges.

    Arguments:
        <branch>        The branch you want to merge in.

    """
    def __init__(self):
        super(Merge, self).__init__()
        self._key = "m"
        self._section = "Merge"

    def description(self):
        return "Merge another local branch into your current branch."

    @log_wrapper
    def execute(self, args):
        # Imported here to avoid circular dependencies
        from vine import grapeMenu

        self.set_progress_file(execution_path=self.workspace_dir)

        # this is necessary due to the unholy relationships between mr, m, and md.
        if "<<cmd>>" not in args:
            args["<<cmd>>"] = 'm'
        otherBranch = args["<branch>"] if args["<branch>"] else utility.userInput("Enter name of branch you would like"
                                                                                  " to merge into this branch")
        args["<branch>"] = otherBranch
        config = config_parser_global.grapeConfig()
        publicBranches = config.getPublicBranchList()
        toks = otherBranch.split("origin/")
        if toks[-1] in publicBranches:
            public = toks[-1]
            publicMapping = config.getMapping(self.SECTION_WORKSPACE, "submodulePublicMappings")
            subpublic = publicMapping[public]
            toks[-1] = subpublic
            subpublic = 'origin/'.join(toks)
        else:
            subpublic = otherBranch

        mdArgs = {}
        mdArgs["--am"] = args["--am"]
        mdArgs["--as"] = args["--as"]
        mdArgs["--at"] = args["--at"]
        mdArgs["--aT"] = args["--aT"]
        mdArgs["--ay"] = args["--ay"]
        mdArgs["--aY"] = args["--aY"]
        mdArgs["--public"] = args["<branch>"]
        mdArgs["--subpublic"] = subpublic
        mdArgs["--recurse"] = not args["--noRecurse"]
        mdArgs["--noRecurse"] = args["--noRecurse"]
        mdArgs["--continue"] = args["--continue"]
        mdArgs["<<cmd>>"] = args["<<cmd>>"]
        mdArgs["--noUpdate"] = args["--noUpdate"]
        mdArgs["--noChecks"] = False
        mdArgs["--squash"] = args["--squash"]

        merge_down_command = grapeMenu.menu().getOption("md")
        merge_down_command.workspace_dir = self.workspace_dir
        return merge_down_command.execute(mdArgs)

    def _resume(self, args, *, workspace_dir):
        # Imported here to avoid circular dependencies
        from vine import grapeMenu

        merge_down_command = grapeMenu.menu().getOption("md")
        merge_down_command.workspace_dir = self.workspace_dir
        merge_down_command._resume(args, workspace_dir=workspace_dir)
        return True

    def _saveProgress(self, args):
        super(Merge, self)._saveProgress(args)

    def setDefaultConfig(self, config):
        pass
