import logging
import os
from vine import config_parser_global
from vine import grapeGit as git
from vine.workspace_dir_handler import WorkspaceDirHandler
from vine.option import Option
from vine.vine_logging import log_wrapper


class Clone(Option, WorkspaceDirHandler):
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

    def get_clone_into_dir_from_url(self, url):
        url = url.split('/')[-1]
        return url.split('.')[0]

    @log_wrapper
    def execute(self, args):
        # Imported here to avoid circular dependencies
        from vine import grapeMenu

        remotepath = args["<url>"]
        destpath = args["<path>"]
        if destpath == os.path.curdir:
            destpath = self.get_clone_into_dir_from_url(remotepath)
        rstr = "--recursive" if args["--recursive"] else ""
        recursively = "recursively" if args["--recursive"] else ""
        logging.info(
            f"Cloning {remotepath} into {destpath} {recursively}")
        git.clone(argstr=rstr, source_repo=remotepath, clone_repo=destpath,
                  execution_path=self.workspace_dir)
        logging.info("Clone succeeded!")

        # Following config tasks done in 'destpath'
        logging.info("Changing directory to %s..." % destpath)
        os.chdir(destpath)
        self.workspace_dir = "."

        config_parser_global.read(workspace_dir=self.workspace_dir)
        # ensure you start on a reasonable publish branch
        menu = grapeMenu.menu(workspace_dir=self.workspace_dir)
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
