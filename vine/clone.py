import logging
from vine import config_parser_global
from vine import grapeGit as git
from vine.command_path_handler import CommandPathHandler
from vine.option import Option
from vine.vine_logging import log_wrapper


class Clone(Option, CommandPathHandler):
    """ grape-clone
    Clones a git repo and configures it for use with git.

    Usage: grape-clone <url> <path> [--recursive] [--allNested]

    Arguments:
        <url>       The URL of the remote repository
        <path>      The directory where you want to clone the repo to.

    Options:
        --recursive   Recursively clone submodules.
        --allNested   Get all nested subprojects.

    """

    def __init__(self):
        super(Clone, self).__init__()
        self._key = "clone"
        self._section = "Getting Started"

    #Clones the default repo into a new local repo
    def description(self):
        return "Clone a repo and configure it for grape"

    @log_wrapper
    def execute(self, args):
        # Imported here to avoid circular dependencies
        from vine import grapeMenu

        remotepath = args["<url>"]
        destpath = args["<path>"]
        rstr = "--recursive" if args["--recursive"] else ""
        recursively = "recursively" if args["--recursive"] else ""
        logging.info(
            f"Cloning {remotepath} into {destpath} {recursively}")
        git.clone(argstr=rstr, source_repo=remotepath, clone_repo=destpath,
                  execution_path=self.command_path)
        logging.info("Clone succeeded!")

        # Following config tasks done in 'destpath'
        self.command_path = destpath

        config_parser_global.read(workspace_dir=self.workspace_dir)
        # ensure you start on a reasonable publish branch
        menu = grapeMenu.menu()
        menu.set_command_path(self.command_path)
        config = config_parser_global.grapeConfig()
        publicBranches = config.getPublicBranchList()
        if publicBranches:
            if "develop" in publicBranches:
                initialBranch = "develop"
            elif "master" in publicBranches:
                initialBranch = "master"
            else:
                initialBranch = publicBranches[0]

        menu.applyMenuChoice("checkout", args=[initialBranch])

        if args["--allNested"]:
            configArgs = ["--uv","--uvArg=--allNestedSubprojects"]
        else:
            configArgs = []
        return menu.applyMenuChoice("config", configArgs)

    def setDefaultConfig(self, config):
        pass
