import os
from grape.vine import config_parser_global
from grape.vine import grapeGit as git
from grape.vine import vine_logging
from grape.vine.option import Option


class Clone(Option):
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

    def execute(self, args):
        # Imported here to avoid circular dependencies
        from grape.vine import grapeMenu

        remotepath = args["<url>"]
        destpath = args["<path>"]
        rstr = "--recursive" if args["--recursive"] else ""
        recursively = "recursively" if args["--recursive"] else ""
        vine_logging.printMsg(
            f"Cloning {remotepath} into {destpath} {recursively}")
        git.clone(f" {rstr} {remotepath} {destpath}")
        vine_logging.printMsg("Clone succeeded!")
        os.chdir(destpath)
        config_parser_global.read()
        # ensure you start on a reasonable publish branch
        menu = grapeMenu.menu()
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
