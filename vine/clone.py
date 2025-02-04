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

    Usage: grape-clone <url> <path> [--recursive] [--allNested] [--filter=<arg>]

    Arguments:
        <url>       The URL of the remote repository
        <path>      The directory where you want to clone the repo to.

    Options:
        --recursive        Recursively clone submodules. Does not clone nested submodules.
        --allNested        Get all nested subprojects.
        --filter=<arg>     Optional clone filter argument.
                           WARNING! This is still experimental and may have issues with grape workflows.
                           In particular, tree:0 has performance issues with git rev-list/log command on specified
                           files (it appears to download each commit separately).

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
        filterArg = args["--filter"]
        if destpath == os.path.curdir:
            destpath = self.get_clone_into_dir_from_url(remotepath)
        fstr = f"--filter={filterArg}" if filterArg else ""

        logging.info(
            f"Cloning {remotepath} into {destpath} {fstr}")
        git.clone(argstr=fstr, source_repo=remotepath, clone_repo=destpath,
                  execution_path=self.workspace_dir)
        logging.info("Clone succeeded!")

        # Following config tasks done in 'destpath'
        # NOTE This chdir is necessary so that both the checkout and config
        # are properly called from the workspace directory. By just setting
        # the workspace_dir to destpath, the checkout occurs in the new
        # clone, but the config call is confused about where the workspace
        # directory should be and creates another subdirectory called
        # destpath (in destpath) when initializing nested subprojects.
        # TODO Figure out what is going on. This may be related to to the
        # python3 refactoring for the workspace_dir handler, which may not
        # be appropriate for clone. Note also that the workspace_dir handler
        # will give different results depending on whether an absolute path
        # or a relative path is given (clone might be the only place that
        # it is possible to provide either).
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

        configArgs = []
        if args["--allNested"]:
            configArgs.append("--uvArg=--allNestedSubprojects")
        if args["--recursive"]:
            configArgs.append("--uvArg=--allSubmodules")

        if configArgs:
            configArgs.insert(0, "--uv")
            if filterArg:
                configArgs.append("--uvArg=--filter={filterArg}")

        return menu.applyMenuChoice("config", configArgs)

    def setDefaultConfig(self, config):
        pass
