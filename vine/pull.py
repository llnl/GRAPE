import logging
from vine import grapeGit as git
from vine import vine_logging
from vine.option import Option
from vine.resumable import Resumable
from vine.vine_logging import log_wrapper


def pull(branch="develop", repo=".", rebase=False):
    if rebase:
        argStr = f"--rebase origin {branch}"
    else:
        argStr = f"origin {branch} "

    logging.info(f"Pulling {branch} in {repo}...")
    git.pull(argStr, throwOnFail=True)


class Pull(Resumable, Option):
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
        mrArgs = {}
        currentBranch = git.currentBranch()
        mrArgs["<branch>"] = currentBranch
        # the <<cmd>> stuff is for consistent --continue output
        if not "<<cmd>>" in args:
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
            git.pull(f"origin {currentBranch}")
            logging.info("Pulled current branch from origin")
            return True
        else:
            # Imported here to avoid circular dependencies
            from vine import grapeMenu

            val =  grapeMenu.menu().getOption("mr").execute(mrArgs)
            if val:
                logging.info("Pulled current branch from origin")
            return val

    def _resume(self, args):
        # Imported here to avoid circular dependencies
        from vine import grapeMenu
        grapeMenu.menu().getOption("md")._resume(args)
        return True

    def _saveProgress(self, args):
        super(Pull, self)._saveProgress(args)

    def setDefaultConfig(self, config):
        pass
